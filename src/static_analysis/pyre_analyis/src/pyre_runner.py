#!/usr/bin/env python3
"""Pyre execution and environment setup for Pyre-Analyst."""

import os
import json
import subprocess
import multiprocessing
import time
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from dependencies import find_pyre_binary
from file_processor import collect_python_files, process_files


class PyreServerManager:
    """Manages Pyre daemon server lifecycle for incremental analysis."""

    def __init__(self, work_dir: Path, config: Dict[str, Any]):
        self.work_dir = work_dir
        self.config = config
        self.pyre_binary = find_pyre_binary()

    def is_server_running(self) -> bool:
        """Check if Pyre server is running in the work directory."""
        if not self.pyre_binary:
            return False

        original_cwd = os.getcwd()
        try:
            os.chdir(self.work_dir)
            result = subprocess.run(
                [self.pyre_binary, "servers"], capture_output=True, text=True, timeout=10
            )
            # Check if current directory is listed in active servers
            return str(self.work_dir) in result.stdout
        except Exception:
            return False
        finally:
            os.chdir(original_cwd)

    def start_server(self) -> bool:
        """Start Pyre daemon server."""
        if not self.pyre_binary:
            print("❌ Error: Pyre binary not found")
            return False

        if self.is_server_running():
            print("✅ Pyre server already running")
            return True

        original_cwd = os.getcwd()
        try:
            os.chdir(self.work_dir)
            print("🚀 Starting Pyre daemon server...")

            result = subprocess.run(
                [self.pyre_binary, "start"],
                capture_output=True,
                text=True,
                timeout=self.config["analysis"]["timeout"],
            )

            if result.returncode == 0:
                print("✅ Pyre server started successfully")
                return True
            else:
                print(f"❌ Failed to start server: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            print(f"⏰ Server start timed out after {self.config['analysis']['timeout']} seconds")
            return False
        except Exception as e:
            print(f"❌ Server start failed: {e}")
            return False
        finally:
            os.chdir(original_cwd)

    def stop_server(self) -> bool:
        """Stop Pyre daemon server."""
        if not self.pyre_binary:
            return False

        if not self.is_server_running():
            print("✅ Pyre server not running")
            return True

        original_cwd = os.getcwd()
        try:
            os.chdir(self.work_dir)
            print("🛑 Stopping Pyre daemon server...")

            result = subprocess.run(
                [self.pyre_binary, "stop"], capture_output=True, text=True, timeout=30
            )

            if result.returncode == 0:
                print("✅ Pyre server stopped successfully")
                return True
            else:
                print(f"⚠️ Server stop warning: {result.stderr}")
                return True  # Often succeeds even with warnings

        except Exception as e:
            print(f"❌ Server stop failed: {e}")
            return False
        finally:
            os.chdir(original_cwd)

    def restart_server(self) -> bool:
        """Restart Pyre daemon server."""
        if not self.pyre_binary:
            return False

        original_cwd = os.getcwd()
        try:
            os.chdir(self.work_dir)
            print("🔄 Restarting Pyre daemon server...")

            result = subprocess.run(
                [self.pyre_binary, "restart"],
                capture_output=True,
                text=True,
                timeout=self.config["analysis"]["timeout"],
            )

            if result.returncode == 0:
                print("✅ Pyre server restarted successfully")
                return True
            else:
                print(f"❌ Server restart failed: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            print(f"⏰ Server restart timed out after {self.config['analysis']['timeout']} seconds")
            return False
        except Exception as e:
            print(f"❌ Server restart failed: {e}")
            return False
        finally:
            os.chdir(original_cwd)


def setup_pyre_environment(
    temp_dir: Path, config: Dict[str, Any], line_mappings: Optional[Dict[str, List]] = None
) -> None:
    """Setup Pyre configuration and taint files."""

    cpu_count = multiprocessing.cpu_count()

    pyre_config = {
        "source_directories": ["."],
        "taint_models_path": ["taint"],
        "strict": False,
        "workers": min(cpu_count, 8),
        "exclude": [".*\\.pyc", ".*/__pycache__/.*", ".*/\\..*"],
        "ignore_all_errors": [".*"],
        "search_path": [],
        "only_check_paths": ["."],
    }

    print(f"🚀 Configuring Pyre with {pyre_config['workers']} workers")

    with open(temp_dir / ".pyre_configuration", "w") as f:
        json.dump(pyre_config, f, indent=2)

    _setup_taint_rules(temp_dir, config)


def _setup_taint_rules(temp_dir: Path, config: Dict[str, Any]) -> None:
    """Create taint directory and rules."""

    taint_dir = temp_dir / "taint"
    taint_dir.mkdir()

    # Create taint configuration
    taint_config = config["taint_config"]
    with open(taint_dir / "taint.config", "w") as f:
        json.dump(taint_config, f, indent=2)

    # Create taint rules
    taint_rules = "# Taint rules for LLM functions\n\n"

    # Find modules with call_llm and extract_llm_response functions
    modules_with_call_llm = []
    modules_with_extract = []
    for module_file in temp_dir.rglob("*.py"):
        try:
            # Build the dotted module path relative to the temp_dir root
            relative_path = module_file.relative_to(temp_dir)
            if relative_path.stem == "__init__":
                continue

            # Convert path (e.g. pkg/utils/handler.py) to dotted name (pkg.utils.handler)
            module_name = ".".join(relative_path.with_suffix("").parts)

            content = module_file.read_text(encoding="utf-8", errors="ignore")
            if "def call_llm(" in content:
                modules_with_call_llm.append(module_name)
            if "def extract_llm_response(" in content:
                modules_with_extract.append(module_name)
        except Exception:
            # Skip files that cannot be read/processed
            continue

    # Deduplicate modules and create call_llm model exactly once per module
    if modules_with_call_llm:
        modules_with_call_llm = sorted(set(modules_with_call_llm))
        print(f"📝 Adding taint rules for {len(modules_with_call_llm)} modules with call_llm")

    # Model call_llm as both Source and Sink
    for module_name in modules_with_call_llm:
        taint_rules += (
            f"def {module_name}.call_llm(provider, content: TaintSink[LLMInput]) -> "
            "TaintSource[LLMOutput]: ...\n"
        )

    # Deduplicate before generating models for extract helper
    modules_with_extract = sorted(set(modules_with_extract))

    # Model extract_llm_response as passthrough (TITO)
    for module_name in modules_with_extract:
        taint_rules += (
            f"def {module_name}.extract_llm_response(data: TaintInTaintOut[LocalReturn]): ...\n"
        )

    with open(taint_dir / "taint.pysa", "w") as f:
        f.write(taint_rules)


def run_pyre_analysis(
    work_dir: Path,
    config: Dict[str, Any],
    use_daemon: bool = True,
    changed_files: Optional[List[str]] = None,
) -> Tuple[List[Dict[str, Any]], float]:
    """Run Pyre analysis with optional daemon mode and incremental analysis."""

    start_time = time.time()
    pyre_binary = find_pyre_binary()

    if not pyre_binary:
        print("❌ Pyre binary not found")
        return [], 0.0

    original_cwd = Path(os.getcwd())

    try:
        os.chdir(work_dir)

        if use_daemon and config.get("analysis", {}).get("incremental", False):
            print("🚀 Using Pyre daemon mode for incremental analysis")
            results = _run_incremental_analysis(pyre_binary, config, changed_files, original_cwd)
        else:
            print("🔍 Running standard Pyre taint analysis")
            results = _run_standard_analysis(pyre_binary, config, original_cwd)

        duration = time.time() - start_time
        return results, duration

    finally:
        os.chdir(original_cwd)


def _run_incremental_analysis(
    pyre_binary: str,
    config: Dict[str, Any],
    changed_files: Optional[List[str]] = None,
    original_cwd: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Run Pyre taint analysis with daemon server for incremental benefits."""

    print("🔍 Running Pyre incremental taint analysis...")

    # Start daemon server for faster subsequent runs
    manager = PyreServerManager(Path.cwd(), config)

    # Ensure server is running (this provides incremental benefits)
    if not manager.start_server():
        print("⚠️ Daemon failed to start, falling back to standard analysis")
        return _run_standard_analysis(pyre_binary, config, original_cwd)

    try:
        # Create results directory
        results_dir = Path.cwd() / "pyre_results"
        results_dir.mkdir(exist_ok=True)

        # Build pyre analyze command with daemon server benefits
        pyre_args = [
            pyre_binary,
            "analyze",
            "--save-results-to",
            str(results_dir),
            "--output-format",
            "json",
        ]

        # Add additional performance flags
        workers = config.get("analysis", {}).get("max_workers", "auto")
        if workers != "auto":
            pyre_args.extend(["--workers", str(workers)])

        # Add file filtering for true incremental analysis
        if changed_files and len(changed_files) > 0:
            print(f"🎯 Analyzing only {len(changed_files)} changed files")
            for file_path in changed_files:
                pyre_args.extend(["--filter-files", file_path])

        print(f"📊 Running: {' '.join(pyre_args)}")

        # Run the analysis with daemon server benefits
        process = subprocess.run(
            pyre_args,
            capture_output=True,
            text=True,
            timeout=config.get("analysis", {}).get("timeout", 300),
        )

        print(f"⏱️ Pyre incremental analysis completed (exit code: {process.returncode})")

        # Debug: Show what files are in results directory
        if results_dir.exists():
            result_files = list(results_dir.glob("*"))
            print(f"📁 Results directory contains: {[f.name for f in result_files]}")

        # Look for the taint-output.json file
        taint_output_file = results_dir / "taint-output.json"

        if taint_output_file.exists():
            print(f"✅ Found taint analysis results: {taint_output_file}")

            # Save raw results to timestamped file for analysis
            if original_cwd:
                _save_raw_results(taint_output_file, original_cwd)

            try:
                with open(taint_output_file, "r") as f:
                    content = f.read().strip()

                # Handle multiple JSON objects (one per line)
                if "\n" in content:
                    lines = content.split("\n")
                    results = []
                    for line in lines:
                        line = line.strip()
                        if line:
                            try:
                                data = json.loads(line)
                                if isinstance(data, list):
                                    results.extend(data)
                                elif isinstance(data, dict):
                                    results.append(data)
                            except json.JSONDecodeError:
                                continue
                else:
                    # Single JSON object
                    results = json.loads(content)

                if isinstance(results, list):
                    # Filter for LLM-related flows only
                    llm_flows = _filter_llm_flows(results)
                    print(
                        f"🎯 Found {len(llm_flows)} LLM-related flows (filtered from {len(results)} total)"
                    )
                    return llm_flows
                else:
                    print("⚠️ Unexpected taint-output.json format")
                    return []

            except json.JSONDecodeError as e:
                print(f"❌ Failed to parse taint-output.json: {e}")
                print("🔍 File content preview:")
                with open(taint_output_file, "r") as f:
                    preview = f.read(200)
                    print(f"   {preview}...")
                return []
        else:
            print(f"⚠️ taint-output.json not found in {results_dir}")
            print(f"📋 Pyre stderr: {process.stderr}")
            return []

    except subprocess.TimeoutExpired:
        print("⏱️ Pyre analysis timed out")
        return []
    except Exception as e:
        print(f"❌ Error during incremental analysis: {e}")
        return []


def _run_standard_analysis(
    pyre_binary: str, config: Dict[str, Any], original_cwd: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """Run standard Pyre taint analysis without daemon."""

    print("🔍 Running Pyre standard taint analysis...")

    # Create results directory
    results_dir = Path.cwd() / "pyre_results"
    results_dir.mkdir(exist_ok=True)

    # Build command for standard analysis
    pyre_args = [
        pyre_binary,
        "analyze",
        "--save-results-to",
        str(results_dir),
        "--output-format",
        "json",
    ]

    workers = config.get("analysis", {}).get("max_workers", "auto")
    if workers != "auto":
        pyre_args.extend(["--workers", str(workers)])

    try:
        process = subprocess.run(
            pyre_args,
            capture_output=True,
            text=True,
            timeout=config.get("analysis", {}).get("timeout", 300),
        )

        print(f"⏱️ Pyre standard analysis completed (exit code: {process.returncode})")

        # Look for results
        taint_output_file = results_dir / "taint-output.json"

        if taint_output_file.exists():
            # Save raw results to timestamped file for analysis
            if original_cwd:
                _save_raw_results(taint_output_file, original_cwd)

            try:
                with open(taint_output_file, "r") as f:
                    content = f.read().strip()

                # Handle multiple JSON objects (one per line)
                if "\n" in content:
                    lines = content.split("\n")
                    results = []
                    for line in lines:
                        line = line.strip()
                        if line:
                            try:
                                data = json.loads(line)
                                if isinstance(data, list):
                                    results.extend(data)
                                elif isinstance(data, dict):
                                    results.append(data)
                            except json.JSONDecodeError:
                                continue
                else:
                    # Single JSON object
                    results = json.loads(content)

                if isinstance(results, list):
                    # Filter for LLM-related flows only
                    llm_flows = _filter_llm_flows(results)
                    return llm_flows

            except json.JSONDecodeError as e:
                print(f"❌ Failed to parse taint-output.json: {e}")
                return []

        print(f"⚠️ No taint results found. Stderr: {process.stderr}")
        return []

    except subprocess.TimeoutExpired:
        print("⏱️ Pyre analysis timed out")
        return []
    except Exception as e:
        print(f"❌ Error during standard analysis: {e}")
        return []


def analyze_codebase_incremental(
    target_path: str, config: Dict[str, Any], changed_files: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """Analyze codebase with incremental support - only re-analyze changed files."""

    target = Path(target_path)
    if not target.exists():
        print(f"❌ Target path does not exist: {target_path}")
        return []

    # Use persistent cache directory for incremental benefits
    cache_dir = Path(".pyre_analysis_cache")

    # Create temporary directory for this analysis
    temp_dir = Path(tempfile.mkdtemp(prefix="pyre_analysis_"))
    print(f"📁 Created analysis directory: {temp_dir}")

    try:
        # Collect and process Python files (only changed ones if specified)
        if changed_files:
            # Filter to only process changed files
            python_files = []
            for changed_file in changed_files:
                changed_path = Path(changed_file)
                if changed_path.suffix == ".py" and changed_path.exists():
                    python_files.append(changed_path)
            print(f"🎯 Analyzing {len(python_files)} changed files (incremental mode)")
        else:
            python_files = collect_python_files(target)
            print(f"🔍 Found {len(python_files)} Python files for analysis")

        if not python_files:
            print("⚠️ No Python files to analyze")
            return []

        # Process files with our transformations
        processed_files = process_files(python_files, target, temp_dir, config)

        # Set up Pyre environment
        setup_pyre_environment(temp_dir, config, processed_files if processed_files else None)

        # Run incremental analysis with daemon support
        results, duration = run_pyre_analysis(
            temp_dir, config, use_daemon=True, changed_files=changed_files
        )  # Use daemon for incremental benefits  # Pass changed files for filtering

        print(f"⏱️ Analysis completed in {duration:.2f} seconds")

        if results:
            print(f"✅ Found {len(results)} LLM data flows (incremental)")
        else:
            print("✅ No flows detected (incremental)")

        return results

    finally:
        # Clean up temporary directory
        shutil.rmtree(temp_dir, ignore_errors=True)
        print("🧹 Cleaned up temporary directory")


def _save_raw_results(taint_output_file: Path, original_cwd: Path) -> None:
    """Save raw Pyre taint-output.json to timestamped results folder."""

    import datetime
    import shutil

    # Create results directory
    results_dir = original_cwd / "results"
    results_dir.mkdir(exist_ok=True)

    # Create timestamped filename
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_file = results_dir / f"raw_taint_output_{timestamp}.json"

    try:
        # Copy the raw file
        shutil.copy2(taint_output_file, raw_file)
        print(f"💾 Raw taint results saved to: {raw_file}")

        # Also save the absolute path for clarity
        print(f"📁 Full path: {raw_file.absolute()}")

    except Exception as e:
        print(f"❌ Failed to save raw results: {e}")
        print(f"   Source: {taint_output_file}")
        print(f"   Target: {raw_file}")

        # Try to save to current directory as fallback
        try:
            fallback_file = Path.cwd() / f"raw_taint_output_{timestamp}.json"
            shutil.copy2(taint_output_file, fallback_file)
            print(f"💾 Fallback: Raw results saved to current directory: {fallback_file}")
        except Exception as fallback_error:
            print(f"❌ Fallback also failed: {fallback_error}")


def _filter_llm_flows(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter taint analysis results to only include LLM-related flows."""

    llm_flows = []

    for result in results:
        # Check if this is an LLM-related flow
        if _is_llm_flow(result):
            llm_flows.append(result)

    return llm_flows


def _is_llm_flow(result: Dict[str, Any]) -> bool:
    """Check if a taint flow result is LLM-related."""

    # Handle the new JSON stream format
    if "kind" in result and "data" in result:
        if result["kind"] == "issue":
            data = result["data"]
        else:
            # Not an issue, so not a flow we care about for reporting
            return False
    else:
        # Keep compatibility with older format
        data = result

    # Look for LLM-related keywords in description, name, or message
    text_fields = [
        data.get("description", ""),
        data.get("name", ""),
        data.get("message", ""),
        data.get("message_format", ""),
    ]

    llm_keywords = [
        "llm",
        "llminput",
        "llmoutput",
        "call_llm",
        "openai",
        "anthropic",
        "completions",
        "chat.completions",
    ]

    for text in text_fields:
        if text and isinstance(text, str):
            text_lower = text.lower()
            for keyword in llm_keywords:
                if keyword in text_lower:
                    return True

    # Check sources and sinks if available
    sources = data.get("sources", [])
    sinks = data.get("sinks", [])

    for source in sources:
        if isinstance(source, dict):
            source_kinds = source.get("kinds", [])
            for kind in source_kinds:
                if isinstance(kind, dict):
                    kind_name = kind.get("kind", "").lower()
                    if any(keyword in kind_name for keyword in llm_keywords):
                        return True

    for sink in sinks:
        if isinstance(sink, dict):
            sink_kinds = sink.get("kinds", [])
            for kind in sink_kinds:
                if isinstance(kind, dict):
                    kind_name = kind.get("kind", "").lower()
                    if any(keyword in kind_name for keyword in llm_keywords):
                        return True

    # Check if the flow involves call_llm functions
    define_field = data.get("define", "")
    if define_field and "call_llm" in define_field:
        return True

    return False


def cleanup_pyre_server(temp_dir: Path, config: Dict[str, Any]) -> None:
    """Clean up Pyre daemon server."""
    try:
        manager = PyreServerManager(temp_dir, config)
        manager.stop_server()
    except Exception as e:
        print(f"⚠️ Warning: Could not clean up Pyre server: {e}")
