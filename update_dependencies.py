#!/usr/bin/env python3
"""
Script to update conda environment and pyproject.toml dependencies.

Usage:
    python update_dependencies.py           # Update production dependencies
    python update_dependencies.py --dev     # Update dev dependencies (add deps to dev that are not in general ones)
"""

import argparse
import subprocess
import sys
from pathlib import Path
import re
import tomlkit
import yaml


def run_command(cmd, check=True):
    """Run shell command and return output."""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=check)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {cmd}")
        print(f"Error: {e.stderr}")
        sys.exit(1)


def get_conda_info():
    """Get current conda environment name and installed packages."""
    env_name = run_command(
        "conda info --json | python -c \"import sys, json; print(json.load(sys.stdin)['active_prefix_name'])\""
    )

    # Use --from-history to get only explicitly installed packages
    try:
        history_output = run_command("conda env export --from-history --no-builds")

        # Parse the YAML to extract dependencies
        env_data = yaml.safe_load(history_output)
        conda_packages = []

        for dep in env_data.get("dependencies", []):
            if isinstance(dep, str):
                # Regular conda package
                conda_packages.append(dep)
            elif isinstance(dep, dict) and "pip" in dep:
                # Skip pip section - we'll handle pip separately
                continue

        return env_name, conda_packages

    except Exception as e:
        print(f"Warning: Could not get conda history, falling back to conda list: {e}")
        # Fallback to previous method if --from-history fails
        conda_list = run_command("conda list --json")
        import json

        packages = json.loads(conda_list)

        conda_packages = []
        for pkg in packages:
            if pkg.get("channel") != "pypi" or pkg["name"] == "pip":
                conda_packages.append(f"{pkg['name']}={pkg['version']}")

        return env_name, conda_packages


def get_pip_dependencies():
    """Get pip dependencies, filtered for pyproject.toml compatibility."""
    # Get all pip packages
    pip_freeze = run_command("pip freeze")

    # Get conda-managed packages to exclude them
    conda_list = run_command("conda list --json")
    import json

    conda_managed = set()

    for pkg in json.loads(conda_list):
        if pkg.get("channel") != "pypi":  # These are conda packages
            conda_managed.add(pkg["name"].lower())

    dependencies = []
    for line in pip_freeze.split("\n"):
        line = line.strip()
        if not line:
            continue

        # Skip problematic patterns that cause pip install errors
        skip_patterns = [
            r"^-e\s+git\+",  # Editable git installs
            r"@\s+file:///",  # Local file installs (conda build artifacts)
            r"^-e\s+\.",  # Current package in editable mode
            r"^\s*#",  # Comments
            r"^.*@.*file:///",  # Any dependency with local file path
            r"^.*@.*croot/",  # Conda build artifacts
        ]

        should_skip = False
        for pattern in skip_patterns:
            if re.match(pattern, line):
                should_skip = True
                break

        if should_skip:
            print(f"  Skipping problematic dependency: {line}")
            continue

        # Extract package name
        pkg_name = re.split(r"[<>=!@]", line)[0].strip().lower()

        # Skip if this package is managed by conda
        if pkg_name in conda_managed:
            print(f"  Skipping conda-managed package: {line}")
            continue

        # Skip specific known problematic packages
        problematic_packages = [
            "swebench",  # Your example
            # Add other known problematic packages here
        ]

        if pkg_name in problematic_packages:
            print(f"  Skipping known problematic package: {line}")
            continue

        dependencies.append(line)

    return dependencies


def create_conda_environment_file(env_name, conda_packages):
    """Create conda-environment.yaml with only conda packages."""
    conda_env = {
        "name": env_name,
        "dependencies": sorted(conda_packages) + ["pip", {"pip": ["-e ."]}],
    }

    with open("conda-environment.yaml", "w") as f:
        yaml.dump(conda_env, f, default_flow_style=False, sort_keys=False)

    print("✓ Created conda-environment.yaml")


def update_pyproject_toml(dependencies, is_dev=False):
    """Update pyproject.toml with pip dependencies."""
    pyproject_path = Path("pyproject.toml")

    if not pyproject_path.exists():
        print("Error: pyproject.toml not found")
        sys.exit(1)

    # Load existing pyproject.toml
    with open(pyproject_path, "r") as f:
        doc = tomlkit.load(f)

    # Ensure project section exists
    if "project" not in doc:
        doc["project"] = tomlkit.table()

    if is_dev:
        # Update dev dependencies
        if "optional-dependencies" not in doc["project"]:
            doc["project"]["optional-dependencies"] = tomlkit.table()

        # Get existing production dependencies to avoid duplicates
        existing_prod_deps = set()
        if "dependencies" in doc["project"]:
            for dep in doc["project"]["dependencies"]:
                # Extract package name (everything before ==, >=, etc.)
                pkg_name = re.split(r"[<>=!]", str(dep))[0].strip()
                existing_prod_deps.add(pkg_name.lower())

        # Filter out dependencies that are already in production
        filtered_deps = []
        for dep in dependencies:
            pkg_name = re.split(r"[<>=!]", dep)[0].strip()
            if pkg_name.lower() not in existing_prod_deps:
                filtered_deps.append(dep)

        doc["project"]["optional-dependencies"]["dev"] = tomlkit.array(sorted(filtered_deps))
        doc["project"]["optional-dependencies"]["dev"].multiline(True)

        print(f"✓ Updated pyproject.toml with {len(filtered_deps)} dev dependencies")
        print(
            f"  (Filtered out {len(dependencies) - len(filtered_deps)} dependencies already in production)"
        )
    else:
        # Update production dependencies
        doc["project"]["dependencies"] = tomlkit.array(sorted(dependencies))
        doc["project"]["dependencies"].multiline(True)

        print(f"✓ Updated pyproject.toml with {len(dependencies)} production dependencies")

    # Write back to file
    with open(pyproject_path, "w") as f:
        tomlkit.dump(doc, f)


def install_npm_dependencies():
    """Install npm dependencies if package.json exists."""
    npm_dir = Path("src/user_interface")
    package_json = npm_dir / "package.json"

    if package_json.exists():
        print(f"✓ Found package.json in {npm_dir}")
        try:
            result = subprocess.run(
                ["npm", "install"], cwd=npm_dir, capture_output=True, text=True, check=True
            )
            print("✓ npm install completed successfully")
        except subprocess.CalledProcessError as e:
            print(f"❌ npm install failed: {e.stderr}")
        except FileNotFoundError:
            print("❌ npm not found. Make sure Node.js is installed.")
    else:
        print(f"ℹ️  No package.json found in {npm_dir}")


def main():
    parser = argparse.ArgumentParser(
        description="Update conda environment and pyproject.toml dependencies"
    )
    parser.add_argument(
        "--dev", action="store_true", help="Update dev dependencies instead of production"
    )
    parser.add_argument("--skip-npm", action="store_true", help="Skip npm install step")
    args = parser.parse_args()

    print(f"Updating {'dev' if args.dev else 'production'} dependencies...")

    # Check if we're in a conda environment
    try:
        env_name, conda_packages = get_conda_info()
        print(f"✓ Found conda environment: {env_name}")
    except Exception as e:
        print(f"Error: Not in a conda environment or conda not available: {e}")
        sys.exit(1)

    # Get pip dependencies
    pip_deps = get_pip_dependencies()
    print(f"✓ Found {len(pip_deps)} pip dependencies")

    # Create conda environment file (only for production run)
    if not args.dev:
        create_conda_environment_file(env_name, conda_packages)

    # Update pyproject.toml
    update_pyproject_toml(pip_deps, args.dev)

    # Install npm dependencies unless skipped
    if not args.skip_npm:
        install_npm_dependencies()

    print("\n✅ Dependencies updated successfully!")
    if args.dev:
        print('To install dev dependencies: pip install -e ".[dev]"')
    else:
        print("To recreate environment: conda env create -f conda-environment.yaml")
        print("To install production dependencies: pip install -e .")
        print("Don't forget to run: cd src/user_interface && npm install")


if __name__ == "__main__":
    main()
