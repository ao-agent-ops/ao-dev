#!/usr/bin/env python3
"""File processing and transformation for Pyre-Analyst."""

import multiprocessing
from pathlib import Path
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from ast_transformer import LLMCallTransformer


def process_files(
    files_to_process: List[Path], target: Path, temp_dir: Path, config: Dict[str, Any]
) -> Dict[str, List]:
    """Process and transform files for analysis.

    Returns:
        Dict containing line mappings for all transformed files
    """

    # Collect line mappings from all transformations
    all_line_mappings = {}

    # Use parallel processing for large codebases
    if len(files_to_process) > 2 and not config.get("analysis", {}).get("sequential", False):
        print("🚀 Using parallel file processing...")
        all_line_mappings = _process_files_parallel(files_to_process, target, temp_dir, config)
    else:
        print("🔄 Using sequential file processing...")
        all_line_mappings = _process_files_sequential(files_to_process, target, temp_dir, config)

    return all_line_mappings


def _process_files_parallel(
    files: List[Path], target: Path, temp_dir: Path, config: Dict[str, Any]
) -> Dict[str, List]:
    """Process files in parallel."""

    def process_file(source_file):
        try:
            # Create a new transformer for each file to track line mappings
            transformer = LLMCallTransformer(config["llm_patterns"], str(source_file))

            dest_file = _get_dest_file(source_file, target, temp_dir)
            dest_file.parent.mkdir(parents=True, exist_ok=True)

            source_code = source_file.read_text(encoding="utf-8")
            transformed_code = transformer.transform(source_code)
            dest_file.write_text(transformed_code, encoding="utf-8")

            # Get transformation locations for line mapping
            transformations = transformer.get_transformation_locations()

            return (
                source_file.name,
                transformed_code != source_code,
                str(source_file),
                transformations,
            )
        except Exception as e:
            print(f"⚠️ Error processing {source_file}: {e}")
            return source_file.name, False, str(source_file), []

    max_workers = config.get("analysis", {}).get("max_workers", "auto")
    if max_workers == "auto":
        max_workers = min(len(files), multiprocessing.cpu_count())

    all_line_mappings = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_file, f): f for f in files}

        for future in as_completed(futures):
            file_name, was_transformed, source_path, transformations = future.result()
            status = "✅ transformed" if was_transformed else "⚠️ unchanged"
            print(f"   📄 {file_name}: {status}")

            if transformations:
                all_line_mappings[source_path] = transformations

    return all_line_mappings


def _process_files_sequential(
    files: List[Path], target: Path, temp_dir: Path, config: Dict[str, Any]
) -> Dict[str, List]:
    """Process files sequentially."""

    all_line_mappings = {}

    for source_file in files:
        try:
            # Create a new transformer for each file to track line mappings
            transformer = LLMCallTransformer(config["llm_patterns"], str(source_file))

            dest_file = _get_dest_file(source_file, target, temp_dir)
            dest_file.parent.mkdir(parents=True, exist_ok=True)

            source_code = source_file.read_text(encoding="utf-8")
            transformed_code = transformer.transform(source_code)

            # Get transformation information
            transformations = transformer.get_transformation_locations()
            if transformations:
                all_line_mappings[str(source_file)] = transformations

            was_transformed = transformed_code != source_code
            status = "✅ transformed" if was_transformed else "⚠️ unchanged"

            if was_transformed and transformer.transformation_count > 0:
                print(f"   📄 {source_file.name}: {status}")
                print(f"🔧 Applied {transformer.transformation_count} LLM call transformations")
                print(
                    f"📊 Tracked {len(transformer.call_llm_vars)} variables with call_llm results"
                )
            else:
                print(f"   📄 {source_file.name}: {status}")

            dest_file.write_text(transformed_code, encoding="utf-8")

        except Exception as e:
            print(f"⚠️ Error processing {source_file}: {e}")
            continue

    return all_line_mappings


def _get_dest_file(source_file: Path, target: Path, temp_dir: Path) -> Path:
    """Get destination file path in temp directory."""
    if target.is_file():
        return temp_dir / source_file.name
    else:
        rel_path = source_file.relative_to(target)
        return temp_dir / rel_path


def collect_python_files(target: Path) -> List[Path]:
    """Collect all Python files from target path."""
    if target.is_file():
        return [target]
    else:
        return list(target.rglob("*.py"))
