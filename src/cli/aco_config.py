# Register taint functions in builtins BEFORE any other imports
import builtins
import sys
import os

# Add current directory to path to import modules directly
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Import directly from file path to avoid triggering aco.__init__.py
import importlib.util

ast_transformer_path = os.path.join(current_dir, "server", "ast_transformer.py")
if os.path.exists(ast_transformer_path):
    spec = importlib.util.spec_from_file_location("ast_transformer", ast_transformer_path)
    ast_transformer = importlib.util.module_from_spec(spec)
    sys.modules["ast_transformer"] = ast_transformer
    spec.loader.exec_module(ast_transformer)

    builtins.taint_fstring_join = ast_transformer.taint_fstring_join
    builtins.taint_format_string = ast_transformer.taint_format_string
    builtins.taint_percent_format = ast_transformer.taint_percent_format
    builtins.exec_func = ast_transformer.exec_func

# Now safe to import other modules
import argparse
import os
from aco.common.config import (
    Config,
    _ask_field,
    _convert_to_valid_path,
)
from aco.common.constants import ACO_CONFIG, ACO_PROJECT_ROOT


def get_user_input() -> Config:
    project_root = _ask_field(
        f"What is the root directory of your project? [{ACO_PROJECT_ROOT}]\n> ",
        _convert_to_valid_path,
        default=ACO_PROJECT_ROOT,
        error_message="Please enter a valid path to a directory.",
    )

    database_url = _ask_field(
        "Database URL (leave empty for SQLite)\n> ",
        str,
        default=os.environ.get("DATABASE_URL"),
        error_message="Please enter a valid database URL or leave empty.",
    )

    config = Config(
        project_root=project_root,
        database_url=database_url,
    )
    return config


def config_command():
    config = get_user_input()
    config_file = ACO_CONFIG
    config.to_yaml_file(config_file)


def config_command_parser():
    description = (
        "Run `aco config` before you debug your agents. This "
        "will prompt some configurations that you can choose. "
        "These will get saved in a default path or in --config_path "
        "which you can pass: `aco config --config_path some/path/config.yaml"
    )
    parser = argparse.ArgumentParser("Config", usage="aco-config", description=description)
    return parser


def main():
    parser = config_command_parser()
    parser.parse_args()
    config_command()


if __name__ == "__main__":
    main()
