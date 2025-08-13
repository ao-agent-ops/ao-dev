#!/usr/bin/env python3
"""Dependency checking for Pyre-Analyst."""

import subprocess
from pathlib import Path
from typing import Optional


def find_pyre_binary() -> Optional[str]:
    """Find Pyre binary in virtual environment or system PATH."""

    # Check virtual environment first
    script_dir = Path(__file__).parent.parent
    venv_pyre = script_dir / "venv" / "bin" / "pyre"

    if venv_pyre.exists():
        return str(venv_pyre)

    # Check system PATH
    try:
        result = subprocess.run(["which", "pyre"], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass

    # Check common locations
    common_locations = [
        "/usr/local/bin/pyre",
        "/usr/bin/pyre",
        script_dir / "venv" / "bin" / "pyre",
    ]

    for location in common_locations:
        if Path(location).exists():
            return str(location)

    return None


def check_dependencies() -> bool:
    """Check if all required dependencies are available."""

    # Check for Pyre
    pyre_binary = find_pyre_binary()
    if not pyre_binary:
        print("❌ Error: Pyre not found!")
        print("💡 Please run: ./setup.sh")
        return False

    print(f"✅ Found Pyre: {pyre_binary}")

    # Check for LibCST
    try:
        import libcst

        print("✅ Found LibCST")
    except ImportError:
        print("❌ Error: LibCST not found!")
        print("💡 Please run: ./setup.sh")
        return False

    return True
