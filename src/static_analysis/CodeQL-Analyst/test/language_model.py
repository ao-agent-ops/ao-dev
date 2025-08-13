import warnings
import subprocess
import re
from .cache import CACHE
from .colors import bcolors
import tomllib
import boto3
import tomli, toml
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
from code_assistant.common.util import robust_parse_toml

from example_user_file import Agent


agent = Agent()


class TokenLimitException(Exception):
    """Exception raised exceeding token limit."""

    pass


class RateLimitException(Exception):
    """Exception raised exceeding rate limit."""

    pass


class LLMType(Enum):
    GPT_4O = "gpt-4o"
    SONNET = "sonnet"
    SONNETV2 = "sonnetv2"
    SONNET3_7 = "sonnet3.7"
    SONNET3_7_NOTHINK = "sonnet3.7-nothink"
    O3_MINI_HIGH = "o3-mini-high"
    O3_MINI_LOW = "o3-mini-low"
    O3_MINI_MEDIUM = "o3-mini-medium"

    @staticmethod
    def from_string(s):
        if s in ["gpt-4o", "gpt4o"]:
            return LLMType.GPT_4O
        if s in ["claude3", "sonnet"]:
            return LLMType.SONNET
        if s in ["claude3.5", "sonnetv2", "sonnet3.5"]:
            return LLMType.SONNETV2
        if s in ["sonnet3.7", "claude3.7"]:
            return LLMType.SONNET3_7
        if s in ["sonnet3.7-nothink"]:
            return LLMType.SONNET3_7_NOTHINK
        if s in ["o3-mini", "o3", "o3-mini-high"]:
            return LLMType.O3_MINI_HIGH
        if s in ["o3-mini-medium"]:
            return LLMType.O3_MINI_MEDIUM
        if s in ["o3-mini-low"]:
            return LLMType.O3_MINI_LOW
        raise ValueError(f"Unknown LLM type {s}")

    def openhands_model_id(self):
        if self == LLMType.GPT_4O:
            return "openai/gpt-4o"
        if self in [LLMType.O3_MINI_LOW, LLMType.O3_MINI_MEDIUM, LLMType.O3_MINI_HIGH]:
            # NOTE(ferdi): OpenHands does currently not support different reasoning levels.
            # Monitor and add support in the future.
            warnings.warn(f"OpenHands does not support {self}. Will run 'o3-mini'")
            return "o3-mini"

        raise ValueError(f"Model {self} is currently not supported for OpenHands.")

    def is_openai(self):
        return self in [
            LLMType.GPT_4O,
            LLMType.O3_MINI_HIGH,
            LLMType.O3_MINI_MEDIUM,
            LLMType.O3_MINI_LOW,
        ]

    def is_bedrock(self):
        return self in [
            LLMType.SONNET,
            LLMType.SONNETV2,
            LLMType.SONNET3_7,
            LLMType.SONNET3_7_NOTHINK,
        ]

    def model_id(self) -> str:
        if self == LLMType.GPT_4O:
            return "gpt-4o"
        if self == LLMType.SONNET:
            return "anthropic.claude-3-5-sonnet-20240620-v1:0"
        if self == LLMType.SONNETV2:
            return "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
        if self in [LLMType.SONNET3_7, LLMType.SONNET3_7_NOTHINK]:
            return "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
        if self in [LLMType.O3_MINI_HIGH, LLMType.O3_MINI_MEDIUM, LLMType.O3_MINI_LOW]:
            return "o3-mini"
        raise ValueError(f"Unknown LLM type {self}")

    def reasoning_level(self) -> str:
        if self.is_openai():
            if self == LLMType.O3_MINI_HIGH:
                return "high"
            if self == LLMType.O3_MINI_MEDIUM:
                return "medium"
            if self == LLMType.O3_MINI_LOW:
                return "low"
        raise RuntimeError(f"Reasoning level not available for {self}")


class LanguageModel:
    def __init__(self):
        """Initialize the language model."""
        self.config = tomllib.load(open("configs/main.toml", "rb"))
        self.verbose = self.config["verbose"]
        self.llm = LLMType.from_string(self.config["llm"])
        self.use_openhands = self.config["use_openhands"]
        self.low_complexity_llm = LLMType.from_string(self.config["low_complexity_llm"])
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
            # TODO(ferdi): We should probably remove OpenHands ...
            # I cannot support bedrock for now, since I don't have an account.
            assert not self.use_openhands, "OpenHands can currently not use Bedrock"
            self.bedrock_client = boto3.client(
                "bedrock-runtime", region_name="us-east-1", config=bedrock_config
            )
        else:
            self.bedrock_client = None
        self.file_lock = threading.Lock()

    @staticmethod
    def _get_openhands_bash_command(prompt, api_key, model, working_stage):
        """
        Build a Docker run command string with a multi-line prompt.
        """
        # Convert actual newline characters into escaped newlines (\n)
        escaped_prompt = prompt.replace("\n", "\\n")
        cmd = (
            f"docker run -it \\\n"
            f"  --pull=always \\\n"
            f"  -e SANDBOX_RUNTIME_CONTAINER_IMAGE=docker.all-hands.dev/all-hands-ai/runtime:0.27-nikolaik \\\n"
            f'  -e WORKSPACE_MOUNT_PATH="{working_stage}" \\\n'
            f"  -e LLM_API_KEY={api_key} \\\n"
            f"  -e LLM_MODEL={model} \\\n"
            f"  -e LOG_ALL_EVENTS=true \\\n"
            f"  -v {working_stage}:/opt/workspace_base \\\n"
            f"  -v /var/run/docker.sock:/var/run/docker.sock \\\n"
            f"  -v ~/.openhands-state:/.openhands-state \\\n"
            f"  --add-host host.docker.internal:host-gateway \\\n"
            f"  --name openhands-app-$(date +%Y%m%d%H%M%S) \\\n"
            f"  docker.all-hands.dev/all-hands-ai/openhands:0.27 \\\n"
            f'  python -m openhands.core.main -t "{escaped_prompt}"'
        )
        return cmd

    @staticmethod
    def _run_docker_command(prompt, api_key, model, working_stage):
        command = LanguageModel._get_openhands_bash_command(prompt, api_key, model, working_stage)

        try:
            # Run the command in a bash shell and capture the output
            result = subprocess.run(
                command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            output = result.stdout + "\n" + result.stderr

            # Remove color codes
            ansi_escape = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
            output = ansi_escape.sub("", output)
            return output

        except Exception as e:
            raise Exception(f"Couldn't run OpenHands bash command:\n{command}") from e

    @staticmethod
    def _parse_output(output):
        """
        Parse out answer from OpenHands bash output.
        """
        # Check if it wrote code to a file. Return code as string.
        pattern = r"Created File with Text:\s*```(.*?)```"
        match = re.search(pattern, output, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Didn't write code to file. Check if it returned a message.
        pattern = (
            r"\*\*MessageAction\*\* \(source=EventSource\.AGENT\)\n"
            r"CONTENT:\s*(.*?)"
            r"(?=\n\d{2}:\d{2}:\d{2} -)"
        )

        matches = re.findall(pattern, output, re.DOTALL)

        if len(matches) > 0:
            warnings.warn("OpenHands didn't write to file --- output likely to be wrong.")
            return matches[-1].strip()

        # Couldn't parse response. Raise error.
        print("Below is the OpenHands bash output:")
        print(output)
        raise LookupError("Couldn't find response in OpenHands bash output.")

    def _invoke_with_openhands(self, system_msg: str, prompt: str, llm: LLMType) -> str:
        """Get a response using OpenHands."""
        # NOTE: System msg just preprended for now.
        prompt = f"{system_msg}\n\n{prompt}"
        model_id = llm.openhands_model_id()

        # Mount for files in Docker file system.
        working_stage = os.path.dirname(os.path.abspath(__file__))
        working_stage = os.path.join(working_stage, "../working_stage/openhands")
        if not os.path.exists(working_stage):
            os.makedirs(working_stage)

        # Run.
        response, error = None, None
        try:
            response = self._run_docker_command(prompt, self.api_key, model_id, working_stage)
            response = self._parse_output(response)
        except Exception as e:
            error = e

        return response, error

    def _invoke_openai(self, system_msg: str, prompt: str, temperature: float, llm: LLMType) -> str:
        """Invoke the LLM using OpenAI."""
        if not self.within_prompt_limits(prompt, system_msg):
            raise TokenLimitException("Token limit exceeded (OpenAI).")
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
        except openai.BadRequestError as e:
            e_str = str(e)
            if "token" in e_str.lower():
                error = TokenLimitException(f"Token Limit Error (OpenAI): {e}")
            else:
                error = e
        except openai.RateLimitError as e:
            error = RateLimitException(f"Rate Limit Error (OpenAI): {e}")
        except Exception as e:
            error = e
        return response, error

    def _invoke_bedrock(
        self, system_msg: str, prompt: str, temperature: float, llm: LLMType
    ) -> str:
        """Invoke the LLM using Bedrock."""
        if not self.within_prompt_limits(prompt, system_msg):
            raise TokenLimitException(
                f"Token limit exceeded (Bedrock). Prompt length: {len(prompt) + len(system_msg)}."
            )
        response, error = None, None
        model_id = llm.model_id()
        try:
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "system": system_msg,
                "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
                "max_tokens": 100000,  # TODO: Make this configurable.
            }
            if llm == LLMType.SONNET3_7:
                body["thinking"] = {
                    "type": "enabled",
                    "budget_tokens": 90000,  # TODO: Make this configurable.
                }
            else:
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
            if "ThrottlingException" in f"{e}":
                # Treat as a rate limit error
                error = RateLimitException(f"Rate Limit Error (Bedrock): {e}")
            if "ServiceUnavailableException" in f"{e}":
                # Treat as a rate limit error
                error = RateLimitException(f"Rate Limit Error (Bedrock): {e}")
        return response, error

    def _embed_openai(self, text: str):
        """Embed text using OpenAI."""
        if not self.within_embedding_limits(text):
            raise TokenLimitException("Embedding token limit exceeded (OpenAI).")
        response, error = None, None
        try:
            response = (
                self.openai_client.embeddings.create(
                    input=[text],
                    model="text-embedding-3-large",
                    dimensions=1024,
                )
                .data[0]
                .embedding
            )
        except openai.BadRequestError as e:
            error = TokenLimitException(f"Embedding Limit Error (OpenAI): {e}")
        except openai.RateLimitError as e:
            error = RateLimitException(f"Embedding Rate Limit Error (OpenAI): {e}")
        except openai.InternalServerError as e:
            error = RateLimitException(f"Embedding Rate Limit Error (OpenAI): {e}")
        except Exception as e:
            error = e
        return response, error

    def _embed_bedrock(self, text: str):
        """Embed text using Bedrock."""
        if not self.within_embedding_limits(text):
            raise TokenLimitException("Embedding token limit exceeded (Bedrock).")
        response, error = None, None
        try:
            body = json.dumps(
                {
                    "inputText": text,
                    "dimensions": 1024,
                    "normalize": True,
                }
            )
            response = self.bedrock_client.invoke_model(
                body=body,
                modelId="amazon.titan-embed-text-v2:0",
                accept="application/json",
                contentType="application/json",
            )
            response = json.loads(response.get("body").read())
            response = response.get("embedding")
        except Exception as e:
            error = e
            if "ThrottlingException" in f"{e}":
                error = TokenLimitException(f"Embedding Rate Limit Error (Bedrock): {e}")
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
            if cached is not None:
                if self.verbose:
                    print(f"{bcolors.OKBLUE}Using cached response for {cache_key}.{bcolors.ENDC}")
                return cached
        if self.verbose:
            print(
                f"{bcolors.OKGREEN}{bcolors.BOLD}Prompt:\n{prompt}\nCache Key:{cache_key}\n{bcolors.ENDC}"
            )
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
                if self.use_openhands:
                    response, error = self._invoke_with_openhands(system_msg, prompt, llm=llm)
                elif self.llm.is_openai():
                    response, error = self._invoke_openai(
                        system_msg, prompt, temperature=temperature, llm=llm
                    )
                elif self.llm.is_bedrock():
                    response, error = self._invoke_bedrock(
                        system_msg, prompt, temperature=temperature, llm=llm
                    )
                if error is None or not isinstance(error, RateLimitException):
                    break
                if isinstance(error, RateLimitException):
                    if self.verbose:
                        print(f"{bcolors.WARNING}Rate limit exceeded. Retrying...{bcolors.ENDC}")
                    time.sleep(10)
                    continue
        # Check for errors.
        if error is not None:
            if self.verbose:
                print(f"{bcolors.FAIL}Error: {error}{bcolors.ENDC}")
            raise error
        # Cache response
        if cache_key is not None:
            cache_prompt = f"{system_msg}____{prompt}"
            CACHE.set_prompt(cache_key, cache_prompt, response)
        # Done.
        if self.verbose:
            print(f"{bcolors.OKBLUE}Response: {response}{bcolors.ENDC}")
        return response

    def embed(self, text: str, cache_key: t.Optional[str] = None) -> t.List[float]:
        """Embed text."""
        # Check cache.
        cache_key = cache_key or text  # Cache by either.
        cached_response = CACHE.get_prompt(cache_key, text)
        if cached_response is not None:
            if self.verbose:
                print(f"{bcolors.OKBLUE}Using cached embedding for {cache_key[:100]}{bcolors.ENDC}")
            return cached_response
        if self.verbose:
            print(
                f"{bcolors.OKGREEN}{bcolors.BOLD}Calling Embedding ({cache_key[:100]}):\n{text}{bcolors.ENDC}"
            )
        # Make the call.
        response, error = None, None
        for _ in range(self.max_attempts):
            if self.llm.is_openai():
                response, error = self._embed_openai(text)
            elif self.llm.is_bedrock():
                response, error = self._embed_bedrock(text)
            if error is None or not isinstance(error, RateLimitException):
                break
            if isinstance(error, RateLimitException):
                if self.verbose:
                    print(f"{bcolors.WARNING}Rate limit exceeded. Retrying...{bcolors.ENDC}")
                time.sleep(10)
                continue
        # Check error
        if error is not None:
            if self.verbose:
                print(f"{bcolors.FAIL}Error: {error}{bcolors.ENDC}")
            raise error
        # Cache.
        if cache_key is not None:
            CACHE.set_prompt(cache_key, text, response)
        # Done.
        if self.verbose:
            print(f"{bcolors.OKBLUE}Embedding: {response[:4]}{bcolors.ENDC}")
        return response

    def within_prompt_limits(self, prompt: str, system_msg: t.Optional[str] = None):
        """Check if the prompt is within the limits."""
        # Clause does not support client-side tokenization or limit checking. So I am using a heuristic.
        # This should be a generous enough limit.
        if system_msg is None:
            system_msg = self.default_system_msg
        return len(prompt) + len(system_msg) <= 150_000

    def within_embedding_limits(self, text: str):
        """Check if the text is within the embedding limits."""
        # Clause does not support client-side tokenization or limit checking. So I am using a heuristic.
        # This should be a generous enough limit.
        return len(text) <= 5000

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
                # agent.run(explanation) # YES
                # agent.run(attr)
                # agent.run(block_end)
                if not repeated_tags:
                    reasons[curr_reason_tag] = explanation
                    agent.run(reasons)
                    if len(attr) > 0:
                        attrs[curr_reason_tag] = attr
                else:
                    reasons.setdefault(curr_reason_tag, []).append(explanation)
                    if len(attr) > 0:
                        attrs.setdefault(curr_reason_tag, []).append(attr)
                    response = response[block_end:]
            # agent.run(reasons) # NO
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
        # agent.run(reasons)
        # agent.run(codes)
        # agent.run(attrs)
        return reasons, codes, attrs

    def load_tomli_str(
        self,
        tomli_str: str,
        attempt_no: int = 0,
    ) -> t.Dict[str, t.Any]:
        """Try to load a toml string. If failed, reprompt the LLM to fix the error."""
        if attempt_no >= self.max_attempts:
            assert False, "unable to decode toml string"
        try:
            return robust_parse_toml(tomli_str)
        except Exception as e:
            prompt = f"""
I asked for your response in TOML format. But your response to my prompt has a TomlDecodeError after running tomli.loads
Here is the error message:
----
{e}
----

Here is your response string:
----
{tomli_str}
----

Directly change your response to fix the parsing error, do not modify any content.
<new_response>
```toml
Your updated response
```
</new_response>
Be sure to clearly use the <new_response> tag to contain the answer, and respect the TOML format.
"""
            response = self.invoke(prompt, low_complexity=True)
            _, new_tomli_str, _ = LANGUAGE_MODEL.parse_standard_response(
                response, code_tag="new_response", code_langs=["toml"]
            )
            new_tomli_str = new_tomli_str["new_response"]
            return self.load_tomli_str(new_tomli_str, attempt_no=attempt_no + 1)


dotenv.load_dotenv()
LANGUAGE_MODEL = LanguageModel()
