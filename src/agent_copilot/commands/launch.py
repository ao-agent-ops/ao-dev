import os
import yaml
from argparse import ArgumentParser, REMAINDER
from common.constants import ACO_CONFIG
from agent_copilot.develop_shim import DevelopShim


def launch_command_parser():
    parser = ArgumentParser(
        usage="aco-launch <script.py> [<args>]",
        description="Launch a python script with the agent copilot under the hood.",
        allow_abbrev=False
    )

    parser.add_argument(
        "--config-file",
        default=None,
        help="The config file to use for the default values in the launching script.",
    )

    parser.add_argument(
        "--disable-cache-attachments",
        default=False,
        action="store_true"
    )

    parser.add_argument(
        "-m",
        "--module",
        action="store_true",
        help="Change each process to interpret the launch script as a Python module, executing with the same behavior as 'python -m'.",
    )

    parser.add_argument(
        "script",
        type=str,
        help="The full path to the script to be executed, followed by all the remaining arguments.",
    )

    parser.add_argument("script_args", nargs=REMAINDER, help="Arguments of the script to be executed.")
    return parser


def _validate_launch_command(args):
    default_dict = {}
    config_file = None

    # check if the location of the config file is set
    if (
        args.config_file is not None
        and os.path.isfile(args.config_file)
    ):
        config_file = args.config_file
    # if not, check in the AOC_CONFIG path
    elif os.path.isfile(ACO_CONFIG):
        config_file = ACO_CONFIG
    # if also not, it stays empty and we rely on the (default) args

    if config_file is not None:
        with open(config_file, encoding="utf-8") as f:
            default_dict = yaml.safe_load(f)
    
    # the arguments overwrite what is written in the config file
    # that's why they come second.
    args.__dict__ = {**default_dict, **args.__dict__}
    # we don't need the config_file anymore and we don't
    # want to confuse people with it still in the args:
    del args.config_file
    return args


def launch_command(args):
    args = _validate_launch_command(args)
    shim = DevelopShim(args.script, args.script_args, args.module)
    shim.run()


def main():
    parser = launch_command_parser()
    args = parser.parse_args()
    launch_command(args)


if __name__ == "__main__":
    main()