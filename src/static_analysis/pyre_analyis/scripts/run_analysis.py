#!/usr/bin/env python3

import sys
import argparse
from pathlib import Path
from typing import List, Dict, Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import load_config
from dependencies import check_dependencies
from analyzer import analyze_codebase
from pyre_runner import analyze_codebase_incremental, PyreServerManager
from result_processor import format_console_output, save_results


def main():
    """Main entry point."""

    parser = argparse.ArgumentParser(
        description="Pyre-Analyst: LLM Data Flow Detection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_analysis.py --test                     # Test with example code
  python run_analysis.py /path/to/codebase         # Analyze a codebase
  python run_analysis.py --incremental /path/to/codebase  # Use incremental mode
  python run_analysis.py --incremental /path/to/codebase --changed file1.py file2.py  # Analyze only changed files
  python run_analysis.py --start-daemon            # Start Pyre daemon
  python run_analysis.py --stop-daemon             # Stop Pyre daemon
  python run_analysis.py --daemon-status           # Check daemon status
""",
    )

    # Target and mode options
    parser.add_argument("target", nargs="?", help="Path to Python codebase to analyze")
    parser.add_argument("--test", action="store_true", help="Run test with example code")
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Use incremental analysis mode (faster for repeated runs)",
    )
    parser.add_argument(
        "--changed", nargs="*", help="List of changed files for incremental analysis"
    )

    # Daemon management
    parser.add_argument("--start-daemon", action="store_true", help="Start Pyre daemon server")
    parser.add_argument("--stop-daemon", action="store_true", help="Stop Pyre daemon server")
    parser.add_argument("--daemon-status", action="store_true", help="Check Pyre daemon status")
    parser.add_argument("--restart-daemon", action="store_true", help="Restart Pyre daemon server")

    # Analysis options
    parser.add_argument("--no-daemon", action="store_true", help="Disable daemon mode")

    args = parser.parse_args()

    print("🚀 PYRE-ANALYST: LLM Data Flow Detection")
    print("=" * 60)

    # Load configuration
    config = load_config()

    # Handle daemon management commands
    if args.start_daemon or args.stop_daemon or args.daemon_status or args.restart_daemon:
        handle_daemon_commands(args, config)
        return

    # Check dependencies
    print("🔍 Checking dependencies...")
    if not check_dependencies():
        sys.exit(1)

    # Determine target
    if args.test:
        target_path = run_test_analysis(config, args)
    elif args.target:
        target_path = args.target
    else:
        parser.print_help()
        sys.exit(1)

    print(f"🔍 Analyzing: {target_path}")

    # Run analysis
    results = run_analysis(target_path, config, args)

    # Output results
    output_results(results, target_path, config, args)


def handle_daemon_commands(args, config):
    """Handle daemon management commands."""

    # We need a working directory for daemon operations
    work_dir = Path.cwd()
    manager = PyreServerManager(work_dir, config)

    if args.start_daemon:
        print("🚀 Starting Pyre daemon server...")
        if manager.start_server():
            print("✅ Pyre daemon started successfully")
        else:
            print("❌ Failed to start Pyre daemon")
            sys.exit(1)

    elif args.stop_daemon:
        print("🛑 Stopping Pyre daemon server...")
        if manager.stop_server():
            print("✅ Pyre daemon stopped successfully")
        else:
            print("⚠️ Pyre daemon was not running or could not be stopped")

    elif args.restart_daemon:
        print("🔄 Restarting Pyre daemon server...")
        manager.restart_server()
        print("✅ Pyre daemon restarted successfully")

    elif args.daemon_status:
        print("📊 Checking Pyre daemon status...")
        if manager.is_server_running():
            print("✅ Pyre daemon is running")
        else:
            print("❌ Pyre daemon is not running")


def run_test_analysis(config, args):
    """Run analysis on test code."""

    print("🧪 Using test files from test directory...")

    # Use the actual test directory instead of creating temporary files
    test_dir = Path(__file__).parent.parent / "test"

    if not test_dir.exists():
        print(f"❌ Test directory does not exist: {test_dir}")
        sys.exit(1)

    test_files = list(test_dir.glob("*.py"))
    if not test_files:
        print(f"❌ No Python test files found in: {test_dir}")
        sys.exit(1)

    print(f"📄 Found {len(test_files)} test file(s): {[f.name for f in test_files]}")

    return str(test_dir)


def run_analysis(target_path: str, config: Dict[str, Any], args) -> List[Dict[str, Any]]:
    """Run the appropriate analysis based on arguments."""

    # Determine daemon usage
    use_daemon = not args.no_daemon and config.get("analysis", {}).get("daemon_mode", True)

    try:
        if args.incremental:
            print("⚡ Using incremental analysis mode")
            # Use incremental analysis
            results = analyze_codebase_incremental(target_path, config, changed_files=args.changed)
        else:
            # Use standard analysis
            results = analyze_codebase(target_path, config, use_daemon=use_daemon)

        return results

    except KeyboardInterrupt:
        print("\n⚠️ Analysis interrupted by user")
        return []
    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        return []


def output_results(results: List[Dict[str, Any]], target_path: str, config: Dict[str, Any], args):
    """Output analysis results."""

    print("\n" + "=" * 60)
    print("📊 ANALYSIS RESULTS")
    print("=" * 60)

    if results:
        # Console output
        format_console_output(results)

        # Save results to file if configured
        if config.get("output", {}).get("save_to_file", False):
            output_filename = config.get("output", {}).get("filename")
            save_results(results, target_path, output_path=output_filename)

    else:
        print("✅ No LLM data flows detected")


if __name__ == "__main__":
    main()
