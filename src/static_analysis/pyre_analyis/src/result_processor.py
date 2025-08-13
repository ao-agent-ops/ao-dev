#!/usr/bin/env python3
"""Result processing and formatting for Pyre-Analyst."""

import json
import datetime
from pathlib import Path
from typing import List, Dict, Any


def format_console_output(results: List[Dict[str, Any]]) -> None:
    """Format and display results to console."""

    if not results:
        print("✅ No LLM data flows detected")
        return

    issues = [
        item["data"]
        for item in results
        if isinstance(item, dict) and item.get("kind") == "issue" and "data" in item
    ]

    if not issues:
        print("✅ No LLM data flows detected in the provided results.")
        return

    print(f"🎯 Found {len(issues)} LLM data flow(s):")

    for i, result in enumerate(issues, 1):
        print("-" * 40)
        print(f"Flow {i}: {result.get('message', 'LLM data flow')}")

        # --- Source ---
        source_file, source_line, source_col_start = "N/A", "N/A", "N/A"
        traces = result.get("traces", [])
        forward_trace = next((t for t in traces if t.get("name") == "forward"), None)

        if forward_trace:
            roots = forward_trace.get("roots", [])
            if roots and roots[0]:
                root = roots[0]
                if "origin" in root:
                    origin = root["origin"]
                    source_file = origin.get("filename", "N/A")
                    source_line = origin.get("line", "N/A")
                    source_col_start = origin.get("start", "N/A")
                elif "call" in root and "position" in root["call"]:
                    position = root["call"]["position"]
                    source_file = position.get("filename", "N/A")
                    source_line = position.get("line", "N/A")
                    source_col_start = position.get("start", "N/A")

        # --- Sink ---
        sink_file = result.get("filename", "N/A")
        sink_line = result.get("line", "N/A")
        sink_col_start = result.get("start", "N/A")

        print(f"  Source: {source_file}:{source_line}:{source_col_start}")
        print(f"  Sink:   {sink_file}:{sink_line}:{sink_col_start}")


def save_results(results: List[Dict[str, Any]], target_path: str, output_path: str = None) -> None:
    """Save results to JSON files."""

    if not results:
        print("✅ No flows to save")
        return

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    # Determine output paths
    if output_path:
        base_output = Path(output_path)
    else:
        base_output = Path("results/pyre_analysis_results.json")

    # Use the config filename as a base for the timestamped file
    base_name = base_output.stem
    timestamped_file = base_output.parent / f"{base_name}_{timestamp}.json"

    # Ensure directory exists
    base_output.parent.mkdir(parents=True, exist_ok=True)

    # Create enhanced results
    enhanced_results = _create_enhanced_results(results, target_path, timestamp)

    # Save timestamped file
    with open(timestamped_file, "w") as f:
        json.dump(enhanced_results, f, indent=2, ensure_ascii=False)

    print(f"💾 Results saved to:")
    print(f"   📁 Timestamped: {timestamped_file}")


def _create_enhanced_results(
    results: List[Dict[str, Any]], target_path: str, timestamp: str
) -> Dict[str, Any]:
    """Create enhanced results with metadata and proper formatting."""

    enhanced_flows = []
    for i, result in enumerate(results, 1):
        enhanced_flow = {
            "id": i,
            "name": result.get("name", result.get("callable", "LLM Flow")),
            "file": result.get("path", "unknown"),
            "original_file": result.get("original_path", result.get("path", "unknown")),
            "description": result.get(
                "description", result.get("message", "LLM data flow detected")
            ),
            "rule_code": result.get("code"),
            "function": result.get("define"),
        }

        # Add location information
        if "line" in result and "column" in result:
            enhanced_flow["issue_location"] = {"line": result["line"], "column": result["column"]}

        # Add source/sink details
        for location_type in ["source", "sink"]:
            details_key = f"{location_type}_details"
            if details_key in result:
                enhanced_flow[location_type] = result[details_key]

        # Add flow path
        if "flow_path" in result:
            enhanced_flow["flow_path"] = result["flow_path"]

        enhanced_flows.append(enhanced_flow)

    return {
        "analysis_metadata": {
            "timestamp": timestamp,
            "analysis_target": target_path,
            "flows_detected": len(results),
            "tool_version": "pyre-analyst-1.0.0",
            "analysis_type": "LLM data flow detection",
        },
        "summary": {
            "total_flows": len(results),
            "files_analyzed": len(set(r.get("path", "unknown") for r in results)),
            "unique_sources": len(
                set(
                    r.get("source_details", {}).get("location", "unknown")
                    for r in results
                    if "source_details" in r
                )
            ),
            "unique_sinks": len(
                set(
                    r.get("sink_details", {}).get("location", "unknown")
                    for r in results
                    if "sink_details" in r
                )
            ),
        },
        "flows": enhanced_flows,
    }
