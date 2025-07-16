import subprocess
import yaml
import re

def get_conda_packages():
    """Get top-level Conda packages using --from-history"""
    conda_cmd = ["conda", "env", "export", "--no-builds", "--from-history"]
    result = subprocess.run(conda_cmd, capture_output=True, text=True, check=True)
    lines = [line for line in result.stdout.splitlines() if not line.startswith("prefix:")]
    return yaml.safe_load("\n".join(lines))

def get_clean_pip_packages():
    """Get pip packages from pip freeze and remove problematic ones"""
    pip_cmd = ["pip", "freeze"]
    result = subprocess.run(pip_cmd, capture_output=True, text=True, check=True)
    pip_lines = result.stdout.strip().splitlines()

    clean_lines = []
    for line in pip_lines:
        line = line.strip()
        if not line:
            continue
        if re.search(r'@ file://', line):
            continue  # Skip local file installs
        if line.startswith("-e ") and "git+" not in line:
            continue  # Skip local editable installs
        clean_lines.append(line)
    return clean_lines

def combine_env(conda_env, pip_packages):
    """Insert pip packages into conda environment"""
    dependencies = conda_env.get("dependencies", [])
    
    # Ensure pip is included
    if "pip" not in [pkg.split("=")[0] for pkg in dependencies if isinstance(pkg, str)]:
        dependencies.append("pip")

    # Remove any existing pip section
    dependencies = [d for d in dependencies if not (isinstance(d, dict) and "pip" in d)]

    if pip_packages:
        dependencies.append({"pip": pip_packages})

    conda_env["dependencies"] = dependencies
    return conda_env

def export_combined_env(output_path="conda-environment.yml"):
    conda_env = get_conda_packages()
    pip_packages = get_clean_pip_packages()
    full_env = combine_env(conda_env, pip_packages)

    with open(output_path, "w") as f:
        yaml.dump(full_env, f, sort_keys=False)

    print(f"✅ Clean environment exported to {output_path}")

if __name__ == "__main__":
    export_combined_env()
