import os
import sys
import yaml
from argparse import ArgumentParser, REMAINDER
from typing import Optional
from aco.common.constants import ACO_CONFIG, ACO_PROJECT_ROOT
from aco.common.utils import find_additional_packages_in_project_root
from aco.runner.develop_shim import DevelopShim


def parse_sample_id() -> Optional[int]:
    """Parse the --sample_id flag from command line arguments anywhere in sys.argv."""
    try:
        # Look for --sample_id in sys.argv (handles both --sample_id X and --sample_id=X formats)
        for i, arg in enumerate(sys.argv):
            if arg == "--sample_id" and i + 1 < len(sys.argv):
                # Format: --sample_id X
                return int(sys.argv[i + 1])
            elif arg.startswith("--sample_id="):
                # Format: --sample_id=X
                return int(arg.split("=", 1)[1])
    except (ValueError, IndexError):
        pass
    return None


def launch_command_parser():
    parser = ArgumentParser(
        usage="aco-launch <script.py> [<args>]",
        description="Launch a python script with the agent copilot under the hood.",
        allow_abbrev=False,
    )

    parser.add_argument(
        "--config-file",
        default=None,
        help="The config file to use for the default values in the launching script.",
    )

    parser.add_argument(
        "--project-root",
        default=ACO_PROJECT_ROOT,
        help="The root directory of the user's project.",
    )

    parser.add_argument(
        "-m",
        "--module",
        action="store_true",
        help="Change each process to interpret the launch script as a Python module, executing with the same behavior as 'python -m'.",
    )

    parser.add_argument(
        "script_path",
        type=str,
        help="The full path to the script to be executed, followed by all the remaining arguments.",
    )

    parser.add_argument(
        "script_args", nargs=REMAINDER, help="Arguments of the script to be executed."
    )
    return parser


def _validate_launch_command(args):
    default_dict = {}
    config_file = None

    # check if the location of the config file is set
    if args.config_file is not None and os.path.isfile(args.config_file):
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

    # check the validity of the project_root
    assert os.path.isdir(args.project_root), (
        f"Project root {args.project_root} is not a directory. "
        f"The derived project_root was {ACO_PROJECT_ROOT}. "
        f"To fix this, pass the correct --project-root to aco-launch. "
        "For example, aco-launch --project-root ~/my-project script.py"
    )

    # find additional packages installed in the project root
    args.packages_in_project_root = find_additional_packages_in_project_root(
        project_root=args.project_root
    )

    return args


def launch_command(args):
    args = _validate_launch_command(args)

    # Parse sample_id from command line
    sample_id = parse_sample_id()

    # Note: UI event logging moved to DevelopShim where session_id is available
    shim = DevelopShim(
        script_path=args.script_path,
        script_args=args.script_args,
        is_module_execution=args.module,
        project_root=args.project_root,
        packages_in_project_root=args.packages_in_project_root,
        sample_id=sample_id,
    )
    shim.run()


def main():
    parser = launch_command_parser()
    args = parser.parse_args()
    launch_command(args)


if __name__ == "__main__":
    main()
