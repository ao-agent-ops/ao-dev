#!/usr/bin/env python3
"""Main analyzer orchestration for Pyre-Analyst."""

import os
import tempfile
import shutil
from pathlib import Path
from typing import List, Dict, Any

from file_processor import collect_python_files, process_files
from pyre_runner import (
    setup_pyre_environment,
    run_pyre_analysis,
    cleanup_pyre_server,
    analyze_codebase_incremental,
)


def analyze_codebase(
    target_path: str, config: Dict[str, Any], use_daemon: bool = True
) -> List[Dict[str, Any]]:
    """Main analysis function with daemon mode support."""

    target = Path(target_path)
    if not target.exists():
        print(f"❌ Target path does not exist: {target_path}")
        return []

    # Create temporary directory for analysis
    temp_dir = Path(tempfile.mkdtemp(prefix="pyre_analysis_"))
    print(f"📁 Created analysis directory: {temp_dir}")

    try:
        # Collect and process Python files
        python_files = collect_python_files(target)
        print(f"📄 Processing {len(python_files)} Python files...")

        if not python_files:
            print("⚠️ No Python files found to analyze")
            return []

        # Process files with AST transformations
        line_mappings = process_files(python_files, target, temp_dir, config)

        # Set up Pyre environment in temp directory
        setup_pyre_environment(temp_dir, config, line_mappings)

        # Determine analysis mode
        if use_daemon and config.get("analysis", {}).get("daemon_mode", True):
            print("🚀 Using daemon mode for better performance")

        # Run Pyre analysis
        results, duration = run_pyre_analysis(temp_dir, config, use_daemon)

        # Map results back to original line numbers
        _map_results_to_original_line_numbers(results, line_mappings, target)

        print(f"⏱️ Analysis completed in {duration:.2f} seconds")

        if results:
            print(f"✅ Found {len(results)} LLM data flows")
        else:
            print("✅ No LLM data flows detected")

        return results

    finally:
        # Cleanup - stop any running daemon servers
        cleanup_pyre_server(temp_dir, config)

        # Clean up temporary directory
        shutil.rmtree(temp_dir, ignore_errors=True)
        print("🧹 Cleaned up temporary directory")


# Re-export the incremental analysis function for convenience
def analyze_codebase_incremental_wrapper(
    target_path: str, config: Dict[str, Any], changed_files: List[str] = None
) -> List[Dict[str, Any]]:
    """Wrapper for incremental analysis - delegates to pyre_runner."""
    return analyze_codebase_incremental(target_path, config, changed_files)


def _map_results_to_original_line_numbers(
    results: List[Dict[str, Any]], line_mappings: Dict[str, List], target: Path
) -> None:
    """Map analysis results back to original line numbers and file paths."""

    for result in results:
        if "path" in result:
            # Map file path back to original
            path_str = result["path"]
            original_file_path = None

            # Find the original file path from line mappings
            for source_path, transformations in line_mappings.items():
                source_file = Path(source_path)
                if target.is_dir():
                    try:
                        relative_path = source_file.relative_to(target)
                        if (
                            str(relative_path) == path_str
                            or source_file.name == Path(path_str).name
                        ):
                            original_file_path = source_path
                            result["original_path"] = source_path
                            result["path"] = str(relative_path)
                            break
                    except ValueError:
                        continue
                else:
                    if source_file.name == Path(path_str).name:
                        original_file_path = source_path
                        result["original_path"] = source_path
                        break

            # Map line numbers back to original if we have transformations for this file
            if original_file_path and original_file_path in line_mappings:
                transformations = line_mappings[original_file_path]

                # Get the line number from the result
                line_num = result.get("line", 0)
                if line_num > 0:
                    # Find the closest transformation to map back to original line
                    closest_transformation = None
                    min_distance = float("inf")

                    for orig_line, pattern, transformed in transformations:
                        distance = abs(line_num - orig_line)
                        if distance < min_distance:
                            min_distance = distance
                            closest_transformation = (orig_line, pattern, transformed)

                    if closest_transformation:
                        original_line, pattern, transformed = closest_transformation
                        result["original_line"] = original_line
                        result["transformation_info"] = {
                            "original_pattern": pattern,
                            "transformed_to": transformed,
                            "line_offset": line_num - original_line,
                        }


def _map_results_to_original_paths(results: List[Dict[str, Any]], target: Path) -> None:
    """Map analysis results back to original file paths."""

    if target.is_dir():
        for result in results:
            if "path" in result:
                # Remove analysis cache prefix if present
                path_str = result["path"]
                if ".pyre_analysis_cache" in path_str:
                    # Extract the relative path after the cache directory
                    parts = Path(path_str).parts
                    if ".pyre_analysis_cache" in parts:
                        cache_idx = parts.index(".pyre_analysis_cache")
                        if cache_idx + 1 < len(parts):
                            relative_path = Path(*parts[cache_idx + 1 :])
                            original_path = target / relative_path
                            result["original_path"] = str(original_path)
                            result["path"] = str(relative_path)  # Store relative path for reporting
                else:
                    original_path = target / result["path"]
                    result["original_path"] = str(original_path)
