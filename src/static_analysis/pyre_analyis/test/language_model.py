import warnings
import subprocess
import re

# from .cache import CACHE
# from .colors import bcolors
import tomllib
import boto3

# import tomli, toml
import typing as t
from botocore.config import Config
import os
import openai
from enum import Enum
import json
import dotenv
import time
from collections import OrderedDict
import threading

# from code_assistant.common.util import robust_parse_toml


class LanguageModel:
    def __init__(self):
        """Initialize the language model."""
        self.config = tomllib.load(open("configs/main.toml", "rb"))
        self.verbose = self.config["verbose"]
        # self.llm = LLMType.from_string(self.config["llm"])
        # self.low_complexity_llm = LLMType.from_string(self.config["low_complexity_llm"])
        self.max_attempts = self.config["max_llm_attempts"]
        self.default_system_msg = self.config["default_system_msg"].strip()
        bedrock_config = Config(
            retries={
                "max_attempts": 1,
            },
            read_timeout=1000,
        )
        # The semaphore works as a simple rate limiter.
        # TODO: Still figuring out the right limits.
        self.invoke_semaphore = threading.Semaphore(16)
        if self.llm.is_openai() or self.low_complexity_llm.is_openai():
            # Read OpenAI key from file or env var.
            key_file_path = os.path.join(os.path.dirname(__file__), "openai.key")
            if os.path.exists(key_file_path):
                with open(key_file_path, "r") as key_file:
                    api_key = key_file.read().strip()
            else:
                api_key = os.getenv("OPENAI_API_KEY")
            self.api_key = api_key
            self.client = openai.OpenAI(api_key=api_key, max_retries=0)

        else:
            self.openai_client = None
        if self.llm.is_bedrock() or self.low_complexity_llm.is_bedrock():
            self.bedrock_client = boto3.client(
                "bedrock-runtime", region_name="us-east-1", config=bedrock_config
            )
        else:
            self.bedrock_client = None
        self.file_lock = threading.Lock()

    def _invoke_openai(self, system_msg: str, prompt: str, temperature: float, llm) -> str:
        """Invoke the LLM using OpenAI."""
        # if not self.within_prompt_limits(prompt, system_msg):
        #     raise TokenLimitException("Token limit exceeded (OpenAI).")
        model_id = llm.model_id()
        response, error = None, None
        try:
            if "o3" in model_id:
                extra_kwargs = {
                    "reasoning_effort": llm.reasoning_level(),
                }
                role_name = "developer"
            else:
                extra_kwargs = {
                    "temperature": temperature,
                }
                role_name = "system"
            response = self.openai_client.chat.completions.create(
                model=model_id,
                messages=[
                    {"role": role_name, "content": system_msg},
                    {"role": "user", "content": prompt},
                ],
                **extra_kwargs,
            )
            response = response.choices[0].message.content
        # except openai.BadRequestError as e:
        #     e_str = str(e)
        #     if "token" in e_str.lower():
        #         error = TokenLimitException(f"Token Limit Error (OpenAI): {e}")
        #     else:
        #         error = e
        # except openai.RateLimitError as e:
        #     error = RateLimitException(f"Rate Limit Error (OpenAI): {e}")
        except Exception as e:
            error = e
        return response, error

    def _invoke_bedrock(self, system_msg: str, prompt: str, temperature: float, llm) -> str:
        """Invoke the LLM using Bedrock."""
        # if not self.within_prompt_limits(prompt, system_msg):
        #     raise TokenLimitException(
        #         f"Token limit exceeded (Bedrock). Prompt length: {len(prompt) + len(system_msg)}."
        #     )
        response, error = None, None
        model_id = llm.model_id()
        try:
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "system": system_msg,
                "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
                "max_tokens": 100000,  # TODO: Make this configurable.
            }
            # if llm == LLMType.SONNET3_7:
            #     body['thinking'] = {
            #         'type': 'enabled',
            #         'budget_tokens': 90000, # TODO: Make this configurable.
            #     }
            # else:
            #     body['temperature'] = temperature
            body["temperature"] = temperature
            body = json.dumps(body)
            response = self.bedrock_client.invoke_model(
                modelId=model_id,
                body=body,
            )
            response = json.loads(response["body"].read())
            response = response["content"][-1]["text"]
        except Exception as e:
            error = e
            # if "ThrottlingException" in f"{e}":
            #     # Treat as a rate limit error
            #     error = RateLimitException(f"Rate Limit Error (Bedrock): {e}")
            # if "ServiceUnavailableException" in f"{e}":
            #     # Treat as a rate limit error
            #     error = RateLimitException(f"Rate Limit Error (Bedrock): {e}")
        return response, error

    def invoke(
        self,
        prompt: str,
        cache_key: t.Optional[str] = None,
        system_msg: t.Optional[str] = None,
        temperature=0.0,
        low_complexity=True,
    ) -> str:
        """Invoke the LLM."""
        llm = self.low_complexity_llm if low_complexity else self.llm
        # Default system message
        if system_msg is None:
            system_msg = self.default_system_msg
        # Check cache
        print(cache_key)
        if cache_key is not None:
            cache_key = f"{cache_key}_{llm.value}"
            cache_prompt = f"{system_msg}____{prompt}"
            cached = CACHE.get_prompt(cache_key, cache_prompt)
            cached = prompt
            if cached is not None:
                return cached
        with self.file_lock:
            with open("prompt.txt", "w") as f:
                f.write(system_msg)
                f.write("\n")
                f.write(prompt)
                f.write("\n")
                f.write(cache_key or "")
        # Call LLM
        response, error = None, None
        for _ in range(self.max_attempts):
            with self.invoke_semaphore:
                if self.llm.is_openai():
                    response, error = self._invoke_openai(
                        system_msg, prompt, temperature=temperature, llm=llm
                    )
                elif self.llm.is_bedrock():
                    response, error = self._invoke_bedrock(
                        system_msg, prompt, temperature=temperature, llm=llm
                    )
                return prompt
                if error is None or not isinstance(error, RateLimitException):
                    break
                if isinstance(error, RateLimitException):
                    time.sleep(10)
                    continue
        # Check for errors.
        if error is not None:
            raise error
        # Cache response
        if cache_key is not None:
            cache_prompt = f"{system_msg}____{prompt}"
            CACHE.set_prompt(cache_key, cache_prompt, response)
        return response

    def _parse_block(
        self, output: str, tag: str, langs: t.List[str] = [], tolerate_unclosed_tags: bool = True
    ):
        """Parse code between <tag attrs> and </tag>"""
        start_tag = f"<{tag}"
        end_tag = f"</{tag}>"
        start = output.find(start_tag)
        end = output.find(end_tag)
        if end == -1 and tolerate_unclosed_tags:
            end = len(output)
        if start == -1 or end == -1:
            return None
        # Parse attributes: attr1=value1 attr2=value2
        attrs_start = start + len(start_tag)
        attrs_end = output.find(">", attrs_start)
        attrs = output[attrs_start:attrs_end]
        attrs = attrs.split(" ")
        attrs = {a.split("=")[0]: a.split("=")[1] for a in attrs if "=" in a}
        # Parse content
        start_block = attrs_end + 1
        end_block = output.find(end_tag, start_block)
        block = output[start_block:end_block]
        if block.startswith("\n"):
            block = block[1:]
        if block.endswith("\n"):
            block = block[:-1]
        # Remove possible surroundings. Keep this order.
        block = block.strip()
        lines = block.split("\n")
        # Only remove the surroundings from the first and last line (after strip)
        first_line = lines[0]
        last_line = lines[-1]
        possible_surroundings = [
            "```toml",
            "```json",
            "```diff",
            "```python",
            "```py",
            "```md",
            "```\n",
            "\n```",
        ]
        for lang in langs:
            possible_surroundings = [f"```{lang}"] + possible_surroundings
        for surrounding in possible_surroundings:
            first_line = first_line.replace(surrounding, "```")
            last_line = last_line.replace(surrounding, "```")
        first_line = first_line.replace("```", "")
        last_line = last_line.replace("```", "")
        lines[0] = first_line
        lines[-1] = last_line
        block = "\n".join(lines)
        return block, attrs, attrs_end

    def parse_standard_response(
        self,
        response: str,
        reason_tag: str = "reason",
        code_tag: str = "patch",  # TODO: I think we can delete this.
        code_langs: t.List[str] | str = [],
        tolerate_unclosed_tags: bool = True,
        repeated_tags: bool = False,  # Multiple blocks with the same tag may exist and are parsed together.
    ):
        """Parse a standard LLM response."""
        if isinstance(code_langs, str):
            code_langs = [code_langs]
        reasons = {}
        codes = OrderedDict()
        attrs = {}
        i = -1
        while True:
            if i == -1:
                # Parse overall explanation/code.
                curr_reason_tag = reason_tag
                curr_code_tag = code_tag
            else:
                # Parse individual explanations/code
                if not repeated_tags:
                    # Names are indexed.
                    curr_reason_tag = f"{reason_tag}{i}"
                    curr_code_tag = f"{code_tag}{i}"
            res = self._parse_block(response, curr_reason_tag, langs=["md"])
            if res is not None:
                explanation, attr, block_end = res
                if not repeated_tags:
                    reasons[curr_reason_tag] = explanation
                    if len(attr) > 0:
                        attrs[curr_reason_tag] = attr
                else:
                    reasons.setdefault(curr_reason_tag, []).append(explanation)
                    if len(attr) > 0:
                        attrs.setdefault(curr_reason_tag, []).append(attr)
                    response = response[block_end:]
            res = self._parse_block(
                response,
                curr_code_tag,
                langs=code_langs,
                tolerate_unclosed_tags=tolerate_unclosed_tags,
            )
            if res is not None:
                codeblock, attr, block_end = res
                if not repeated_tags:
                    codes[curr_code_tag] = codeblock
                    if len(attr) > 0:
                        attrs[curr_code_tag] = attr
                else:
                    codes.setdefault(curr_code_tag, []).append(codeblock)
                    if len(attr) > 0:
                        attrs.setdefault(curr_code_tag, []).append(attr)
                    response = response[block_end:]
            else:
                if i >= 0:
                    break
            i += 1
        return reasons, codes, attrs


LANGUAGE_MODEL = LanguageModel()
