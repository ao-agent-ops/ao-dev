import argparse
import yaml
import os
from dataclasses import dataclass
from enum import Enum
from agent_copilot.commands.config.utils import _ask_field, _convert_yes_no_to_bool
from common.constants import ACO_CONFIG


@dataclass
class Config:
    disable_cache_attachments: bool

    @classmethod
    def from_yaml_file(cls, yaml_file: str) -> 'Config':
        with open(yaml_file, encoding="utf-8") as f:
            config_dict = yaml.safe_load(f)
        # maybe here we need to do some processing if we have more involved types
        extra_keys = sorted(set(config_dict.keys()) - set(cls.__dataclass_fields__.keys()))
        if len(extra_keys) > 0:
            raise ValueError(f"The config file at {yaml_file} had unknown keys ({extra_keys}).")
        return cls(**config_dict)

    def to_yaml_file(self, yaml_file: str) -> None:
        # Create parent directories if they don't exist
        os.makedirs(os.path.dirname(yaml_file), exist_ok=True)
        overwrite = True
        if os.path.isfile(yaml_file):
            overwrite = _ask_field(
                input_text=f"Overwrite {yaml_file}? [YES/no]: ",
                convert_value=_convert_yes_no_to_bool,
                default=True,
                error_message="Please enter yes or no."
            )
        if overwrite:
            with open(yaml_file, "w", encoding="utf-8") as f:
                yaml.safe_dump(self.to_dict(), f)
            print(f"Saved config at {yaml_file}")

    def to_dict(self) -> dict:
        result = self.__dict__
        # For serialization, it's best to convert Enums to strings (or their underlying value type).

        def _convert_enums(value):
            if isinstance(value, Enum):
                return value.value
            if isinstance(value, dict):
                if not bool(value):
                    return None
                for key1, value1 in value.items():
                    value[key1] = _convert_enums(value1)
            return value

        for key, value in result.items():
            result[key] = _convert_enums(value)
        result = {k: v for k, v in result.items() if v is not None}
        return result


def get_user_input() -> Config:
    disable_cache_attachments = _ask_field(
        "Caching LLM call attachments like images or pdfs is currently " \
        "the default. Disable? [yes/NO]: ",
        _convert_yes_no_to_bool,
        default=False,
        error_message="Please enter yes or no.",
    )
    config = Config(
        disable_cache_attachments=disable_cache_attachments
    )
    return config


def config_command(args):
    config = get_user_input()
    if args.config_file is not None:
        config_file = args.config_file
    else:
        # get the pare
        config_file = ACO_CONFIG

    config.to_yaml_file(config_file)


def config_command_parser():
    description = "Run `aco config` before you debug your agents. This " \
                    "will prompt some configurations that you can choose. " \
                    "These will get saved in a default path or in --config_path " \
                    "which you can pass: `aco config --config_path some/path/config.yaml"
    parser = argparse.ArgumentParser("Config", usage="aco-config [--config-file <path/to/file.yaml>]", description=description)

    parser.add_argument(
        "--config-file",
        default=None,
        type=str,
        help="The path for the config file.",
    )
    return parser


def main():
    parser = config_command_parser()
    args = parser.parse_args()
    config_command(args)


if __name__ == "__main__":
    main()