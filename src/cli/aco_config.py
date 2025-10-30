import argparse
from aco.common.config import (
    Config,
    _ask_field,
    _convert_yes_no_to_bool,
    _convert_to_valid_path,
    generate_random_username,
)
from aco.common.constants import ACO_CONFIG, ACO_PROJECT_ROOT


def get_user_input() -> Config:
    project_root = _ask_field(
        f"What is the root directory of your project? [{ACO_PROJECT_ROOT}]\n> ",
        _convert_to_valid_path,
        default=ACO_PROJECT_ROOT,
        error_message="Please enter a valid path to a directory.",
    )

    collect_telemetry = _ask_field(
        "Enable telemetry collection? [yes/NO]: ",
        _convert_yes_no_to_bool,
        default=False,
        error_message="Please enter yes or no.",
    )

    telemetry_url = None
    telemetry_key = None
    telemetry_username = None

    if collect_telemetry:
        telemetry_url = _ask_field(
            "Telemetry URL (leave empty for default): ",
            str,
            default=None,
            error_message="Please enter a valid URL or leave empty.",
        )

        telemetry_key = _ask_field(
            "Telemetry key (leave empty for default): ",
            str,
            default=None,
            error_message="Please enter a valid key or leave empty.",
        )

        default_username = generate_random_username()
        telemetry_username = _ask_field(
            f"Telemetry username (leave empty for default '{default_username}'): ",
            str,
            default=default_username,
            error_message="Please enter a valid username or leave empty.",
        )

    config = Config(
        project_root=project_root,
        collect_telemetry=collect_telemetry,
        telemetry_url=telemetry_url,
        telemetry_key=telemetry_key,
        telemetry_username=telemetry_username,
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
