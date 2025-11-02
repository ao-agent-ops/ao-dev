from functools import wraps
from io import BytesIO
import asyncio
from aco.runner.monkey_patching.patching_utils import (
    get_input_dict,
    send_graph_node_and_edges,
    skip_lowlevel_patches,
)
from aco.server.cache_manager import CACHE
from aco.common.logger import logger
from aco.runner.taint_wrappers import get_taint_origins, taint_wrap


# ===========================================================
# Patches for Langchain BaseLanguageModel
# ===========================================================


def langchain_patch():
    try:
        from langchain_core.language_models.chat_models import BaseChatModel
        from langchain_core.language_models.base import BaseLanguageModel
    except ImportError:
        logger.info("Langchain not installed, skipping Langchain patches")
        return

    patch_BaseChatModel_invoke(BaseChatModel)
    patch_BaseLanguageModel_generate(BaseLanguageModel)
    patch_BaseLanguageModel_generate_prompt(BaseLanguageModel)
    patch_BaseChatModel_generate(BaseChatModel)

    # Async patches
    patch_BaseChatModel_ainvoke(BaseChatModel)
    patch_BaseLanguageModel_agenerate(BaseLanguageModel)
    patch_BaseLanguageModel_agenerate_prompt(BaseLanguageModel)
    patch_BaseChatModel_agenerate(BaseChatModel)


def patch_BaseChatModel_invoke(base_chat_model_class):
    try:
        from langchain_core.language_models.chat_models import BaseChatModel
    except ImportError:
        return

    # Original BaseChatModel.invoke function
    original_function = base_chat_model_class.invoke

    # Patched function (executed instead of BaseChatModel.invoke)
    @wraps(original_function)
    def patched_function(self, *args, **kwargs):
        # 1. Set API identifier to fully qualified name of patched function.
        api_type = "langchain.BaseChatModel.invoke"

        # 2. Get full input dict.
        input_dict = get_input_dict(original_function, self, *args, **kwargs)
        model_name = getattr(self, "model_name", None) or getattr(self, "model", None) or "unknown"
        input_dict["model_name"] = model_name

        # 3. Get taint origins (did another LLM produce the input?).
        taint_origins = get_taint_origins(input_dict)

        # 4. Get result from cache or call LLM.
        input_to_use, result, node_id = CACHE.get_in_out(input_dict, api_type)
        if result is None:
            # Set flag to skip low-level patches when called from within Langchain
            skip_lowlevel_patches(True)
            try:
                # Filter out extra fields that shouldn't be passed to the original function
                original_args = {
                    k: v
                    for k, v in input_to_use.items()
                    if k not in ["model_name", "kwargs"] and not k.startswith("_")
                }
                result = original_function(self, **original_args)  # Call LLM.
                CACHE.cache_output(node_id, result)
            finally:
                # Always clear the flag
                skip_lowlevel_patches(False)

        # 5. Tell server that this LLM call happened.
        send_graph_node_and_edges(
            node_id=node_id,
            input_dict=input_dict,
            output_obj=result,
            source_node_ids=taint_origins,
            api_type=api_type,
        )

        # 6. Taint the output object and return it.
        return taint_wrap(result, [node_id])

    # Install patch.
    base_chat_model_class.invoke = patched_function.__get__(None, base_chat_model_class)


def patch_BaseLanguageModel_generate(base_language_model_class):
    try:
        from langchain_core.language_models.base import BaseLanguageModel
    except ImportError:
        return

    # Original BaseLanguageModel.generate function
    original_function = base_language_model_class.generate

    # Patched function (executed instead of BaseLanguageModel.generate)
    @wraps(original_function)
    def patched_function(self, *args, **kwargs):
        # 1. Set API identifier to fully qualified name of patched function.
        api_type = "langchain.BaseLanguageModel.generate"

        # 2. Get full input dict.
        input_dict = get_input_dict(original_function, self, *args, **kwargs)
        model_name = getattr(self, "model_name", None) or getattr(self, "model", None) or "unknown"
        input_dict["model_name"] = model_name

        # 3. Get taint origins (did another LLM produce the input?).
        taint_origins = get_taint_origins(input_dict)

        # 4. Get result from cache or call LLM.
        input_to_use, result, node_id = CACHE.get_in_out(input_dict, api_type)
        if result is None:
            # Set flag to skip low-level patches when called from within Langchain
            skip_lowlevel_patches(True)
            try:
                # Filter out extra fields that shouldn't be passed to the original function
                original_args = {
                    k: v
                    for k, v in input_to_use.items()
                    if k not in ["model_name", "kwargs"] and not k.startswith("_")
                }
                result = original_function(self, **original_args)  # Call LLM.
                CACHE.cache_output(node_id, result)
            finally:
                # Always clear the flag
                skip_lowlevel_patches(False)

        # 5. Tell server that this LLM call happened.
        send_graph_node_and_edges(
            node_id=node_id,
            input_dict=input_dict,
            output_obj=result,
            source_node_ids=taint_origins,
            api_type=api_type,
        )

        # 6. Taint the output object and return it.
        return taint_wrap(result, [node_id])

    # Install patch.
    base_language_model_class.generate = patched_function.__get__(None, base_language_model_class)


def patch_BaseLanguageModel_generate_prompt(base_language_model_class):
    try:
        from langchain_core.language_models.base import BaseLanguageModel
    except ImportError:
        return

    # Original BaseLanguageModel.generate_prompt function
    original_function = base_language_model_class.generate_prompt

    # Patched function (executed instead of BaseLanguageModel.generate_prompt)
    @wraps(original_function)
    def patched_function(self, *args, **kwargs):
        # 1. Set API identifier to fully qualified name of patched function.
        api_type = "langchain.BaseLanguageModel.generate_prompt"

        # 2. Get full input dict.
        input_dict = get_input_dict(original_function, self, *args, **kwargs)
        model_name = getattr(self, "model_name", None) or getattr(self, "model", None) or "unknown"
        input_dict["model_name"] = model_name

        # 3. Get taint origins (did another LLM produce the input?).
        taint_origins = get_taint_origins(input_dict)

        # 4. Get result from cache or call LLM.
        input_to_use, result, node_id = CACHE.get_in_out(input_dict, api_type)
        if result is None:
            # Set flag to skip low-level patches when called from within Langchain
            skip_lowlevel_patches(True)
            try:
                # Filter out extra fields that shouldn't be passed to the original function
                original_args = {
                    k: v
                    for k, v in input_to_use.items()
                    if k not in ["model_name", "kwargs"] and not k.startswith("_")
                }
                result = original_function(self, **original_args)  # Call LLM.
                CACHE.cache_output(node_id, result)
            finally:
                # Always clear the flag
                skip_lowlevel_patches(False)

        # 5. Tell server that this LLM call happened.
        send_graph_node_and_edges(
            node_id=node_id,
            input_dict=input_dict,
            output_obj=result,
            source_node_ids=taint_origins,
            api_type=api_type,
        )

        # 6. Taint the output object and return it.
        return taint_wrap(result, [node_id])

    # Install patch.
    base_language_model_class.generate_prompt = patched_function.__get__(
        None, base_language_model_class
    )


def patch_BaseChatModel_generate(base_chat_model_class):
    try:
        from langchain_core.language_models.chat_models import BaseChatModel
    except ImportError:
        return

    # Original BaseChatModel.generate function
    original_function = base_chat_model_class.generate

    # Patched function (executed instead of BaseChatModel.generate)
    @wraps(original_function)
    def patched_function(self, *args, **kwargs):
        # 1. Set API identifier to fully qualified name of patched function.
        api_type = "langchain.BaseChatModel.generate"

        # 2. Get full input dict.
        input_dict = get_input_dict(original_function, self, *args, **kwargs)
        model_name = getattr(self, "model_name", None) or getattr(self, "model", None) or "unknown"
        input_dict["model_name"] = model_name

        # 3. Get taint origins (did another LLM produce the input?).
        taint_origins = get_taint_origins(input_dict)

        # 4. Get result from cache or call LLM.
        input_to_use, result, node_id = CACHE.get_in_out(input_dict, api_type)
        if result is None:
            # Set flag to skip low-level patches when called from within Langchain
            skip_lowlevel_patches(True)
            try:
                # Filter out extra fields that shouldn't be passed to the original function
                original_args = {
                    k: v
                    for k, v in input_to_use.items()
                    if k not in ["model_name", "kwargs"] and not k.startswith("_")
                }
                result = original_function(self, **original_args)  # Call LLM.
                CACHE.cache_output(node_id, result)
            finally:
                # Always clear the flag
                skip_lowlevel_patches(False)

        # 5. Tell server that this LLM call happened.
        send_graph_node_and_edges(
            node_id=node_id,
            input_dict=input_dict,
            output_obj=result,
            source_node_ids=taint_origins,
            api_type=api_type,
        )

        # 6. Taint the output object and return it.
        return taint_wrap(result, [node_id])

    # Install patch.
    base_chat_model_class.generate = patched_function.__get__(None, base_chat_model_class)


def patch_BaseChatModel_ainvoke(base_chat_model_class):
    try:
        from langchain_core.language_models.chat_models import BaseChatModel
    except ImportError:
        return

    # Original BaseChatModel.ainvoke function
    original_function = base_chat_model_class.ainvoke

    # Patched function (executed instead of BaseChatModel.ainvoke)
    @wraps(original_function)
    async def patched_function(self, *args, **kwargs):
        # 1. Set API identifier to fully qualified name of patched function.
        api_type = "langchain.BaseChatModel.ainvoke"

        # 2. Get full input dict.
        input_dict = get_input_dict(original_function, self, *args, **kwargs)
        model_name = getattr(self, "model_name", None) or getattr(self, "model", None) or "unknown"
        input_dict["model_name"] = model_name

        # 3. Get taint origins (did another LLM produce the input?).
        taint_origins = get_taint_origins(input_dict)

        # 4. Get result from cache or call LLM.
        input_to_use, result, node_id = CACHE.get_in_out(input_dict, api_type)
        if result is None:
            # Set flag to skip low-level patches when called from within Langchain
            skip_lowlevel_patches(True)
            try:
                # Filter out extra fields that shouldn't be passed to the original function
                original_args = {
                    k: v
                    for k, v in input_to_use.items()
                    if k not in ["model_name", "kwargs"] and not k.startswith("_")
                }
                result = await original_function(self, **original_args)  # Call LLM.
                CACHE.cache_output(node_id, result)
            finally:
                # Always clear the flag
                skip_lowlevel_patches(False)

        # 5. Tell server that this LLM call happened.
        send_graph_node_and_edges(
            node_id=node_id,
            input_dict=input_dict,
            output_obj=result,
            source_node_ids=taint_origins,
            api_type=api_type,
        )

        # 6. Taint the output object and return it.
        return taint_wrap(result, [node_id])

    # Install patch.
    base_chat_model_class.ainvoke = patched_function.__get__(None, base_chat_model_class)


def patch_BaseLanguageModel_agenerate(base_language_model_class):
    try:
        from langchain_core.language_models.base import BaseLanguageModel
    except ImportError:
        return

    # Original BaseLanguageModel.agenerate function
    original_function = base_language_model_class.agenerate

    # Patched function (executed instead of BaseLanguageModel.agenerate)
    @wraps(original_function)
    async def patched_function(self, *args, **kwargs):
        # 1. Set API identifier to fully qualified name of patched function.
        api_type = "langchain.BaseLanguageModel.agenerate"

        # 2. Get full input dict.
        input_dict = get_input_dict(original_function, self, *args, **kwargs)
        model_name = getattr(self, "model_name", None) or getattr(self, "model", None) or "unknown"
        input_dict["model_name"] = model_name

        # 3. Get taint origins (did another LLM produce the input?).
        taint_origins = get_taint_origins(input_dict)

        # 4. Get result from cache or call LLM.
        input_to_use, result, node_id = CACHE.get_in_out(input_dict, api_type)
        if result is None:
            # Set flag to skip low-level patches when called from within Langchain
            skip_lowlevel_patches(True)
            try:
                # Filter out extra fields that shouldn't be passed to the original function
                original_args = {
                    k: v
                    for k, v in input_to_use.items()
                    if k not in ["model_name", "kwargs"] and not k.startswith("_")
                }
                result = await original_function(self, **original_args)  # Call LLM.
                CACHE.cache_output(node_id, result)
            finally:
                # Always clear the flag
                skip_lowlevel_patches(False)

        # 5. Tell server that this LLM call happened.
        send_graph_node_and_edges(
            node_id=node_id,
            input_dict=input_dict,
            output_obj=result,
            source_node_ids=taint_origins,
            api_type=api_type,
        )

        # 6. Taint the output object and return it.
        return taint_wrap(result, [node_id])

    # Install patch.
    base_language_model_class.agenerate = patched_function.__get__(None, base_language_model_class)


def patch_BaseLanguageModel_agenerate_prompt(base_language_model_class):
    try:
        from langchain_core.language_models.base import BaseLanguageModel
    except ImportError:
        return

    # Original BaseLanguageModel.agenerate_prompt function
    original_function = base_language_model_class.agenerate_prompt

    # Patched function (executed instead of BaseLanguageModel.agenerate_prompt)
    @wraps(original_function)
    async def patched_function(self, *args, **kwargs):
        # 1. Set API identifier to fully qualified name of patched function.
        api_type = "langchain.BaseLanguageModel.agenerate_prompt"

        # 2. Get full input dict.
        input_dict = get_input_dict(original_function, self, *args, **kwargs)
        model_name = getattr(self, "model_name", None) or getattr(self, "model", None) or "unknown"
        input_dict["model_name"] = model_name

        # 3. Get taint origins (did another LLM produce the input?).
        taint_origins = get_taint_origins(input_dict)

        # 4. Get result from cache or call LLM.
        input_to_use, result, node_id = CACHE.get_in_out(input_dict, api_type)
        if result is None:
            # Set flag to skip low-level patches when called from within Langchain
            skip_lowlevel_patches(True)
            try:
                # Filter out extra fields that shouldn't be passed to the original function
                original_args = {
                    k: v
                    for k, v in input_to_use.items()
                    if k not in ["model_name", "kwargs"] and not k.startswith("_")
                }
                result = await original_function(self, **original_args)  # Call LLM.
                CACHE.cache_output(node_id, result)
            finally:
                # Always clear the flag
                skip_lowlevel_patches(False)

        # 5. Tell server that this LLM call happened.
        send_graph_node_and_edges(
            node_id=node_id,
            input_dict=input_dict,
            output_obj=result,
            source_node_ids=taint_origins,
            api_type=api_type,
        )

        # 6. Taint the output object and return it.
        return taint_wrap(result, [node_id])

    # Install patch.
    base_language_model_class.agenerate_prompt = patched_function.__get__(
        None, base_language_model_class
    )


def patch_BaseChatModel_agenerate(base_chat_model_class):
    try:
        from langchain_core.language_models.chat_models import BaseChatModel
    except ImportError:
        return

    # Original BaseChatModel.agenerate function
    original_function = base_chat_model_class.agenerate

    # Patched function (executed instead of BaseChatModel.agenerate)
    @wraps(original_function)
    async def patched_function(self, *args, **kwargs):
        # 1. Set API identifier to fully qualified name of patched function.
        api_type = "langchain.BaseChatModel.agenerate"

        # 2. Get full input dict.
        input_dict = get_input_dict(original_function, self, *args, **kwargs)
        model_name = getattr(self, "model_name", None) or getattr(self, "model", None) or "unknown"
        input_dict["model_name"] = model_name

        # 3. Get taint origins (did another LLM produce the input?).
        taint_origins = get_taint_origins(input_dict)

        # 4. Get result from cache or call LLM.
        input_to_use, result, node_id = CACHE.get_in_out(input_dict, api_type)
        if result is None:
            # Set flag to skip low-level patches when called from within Langchain
            skip_lowlevel_patches(True)
            try:
                # Filter out extra fields that shouldn't be passed to the original function
                original_args = {
                    k: v
                    for k, v in input_to_use.items()
                    if k not in ["model_name", "kwargs"] and not k.startswith("_")
                }
                result = await original_function(self, **original_args)  # Call LLM.
                CACHE.cache_output(node_id, result)
            finally:
                # Always clear the flag
                skip_lowlevel_patches(False)

        # 5. Tell server that this LLM call happened.
        send_graph_node_and_edges(
            node_id=node_id,
            input_dict=input_dict,
            output_obj=result,
            source_node_ids=taint_origins,
            api_type=api_type,
        )

        # 6. Taint the output object and return it.
        return taint_wrap(result, [node_id])

    # Install patch.
    base_chat_model_class.agenerate = patched_function.__get__(None, base_chat_model_class)
