#!/Users/ferdi/miniconda3/envs/copilot/bin/ python
"""
CodeQL LLM Taint Analysis Tool

This tool uses CodeQL to perform true taint analysis on Python codebases
to detect data flows between LLM API calls (OpenAI and Anthropic).
"""

import argparse
import json
import os
import subprocess
from pathlib import Path
from datetime import datetime


class CodeQLAnalyzer:
    def __init__(self, codeql_path=None):
        self.script_dir = Path(__file__).parent.parent
        self.codeql_path = "/Users/ferdi/Documents/codeql-home/codeql/codeql"  # codeql_path or self.script_dir / "codeql-cli" / "codeql"
        self.codeql_repo = self.script_dir / "codeql-repo"
        self.queries_dir = self.script_dir / "queries"
        self.databases_dir = self.script_dir / "databases"
        self.results_dir = self.script_dir / "results"

        # Create directories if they don't exist
        self.databases_dir.mkdir(exist_ok=True)
        self.results_dir.mkdir(exist_ok=True)

    def check_installation(self):
        """Check if CodeQL is properly installed"""
        result = subprocess.run(
            [str(self.codeql_path), "version"], capture_output=True, text=True, check=True
        )
        print(f"✅ CodeQL version: {result.stdout.strip()}")
        return True
        # except (subprocess.CalledProcessError, FileNotFoundError):
        #     print(f"❌ CodeQL not found at {self.codeql_path}")
        #     print("Please run setup.sh first to install CodeQL")
        #     return False

    def create_database(self, source_path, db_name=None):
        """Create a CodeQL database from the source code"""
        if not db_name:
            db_name = f"db_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        db_path = self.databases_dir / db_name

        print(f"🔍 Creating CodeQL database from {source_path}")
        print(f"📁 Database location: {db_path}")

        cmd = [
            str(self.codeql_path),
            "database",
            "create",
            str(db_path),
            "--language=python",
            f"--source-root={source_path}",
            "--overwrite",
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            print("✅ Database created successfully")
            return db_path
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to create database:")
            print(f"Command: {' '.join(cmd)}")
            print(f"Error: {e.stderr}")
            return None

    def run_query(self, database_path, query_file=None):
        """Run CodeQL query against the database"""
        if not query_file:
            query_file = self.queries_dir / "llm-taint.ql"

        results_file = (
            self.results_dir / f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sarif"
        )

        print(f"🔍 Running query: {query_file}")

        cmd = [
            str(self.codeql_path),
            "database",
            "analyze",
            str(database_path),
            str(query_file),
            f"--search-path={self.codeql_repo}",
            "--format=sarif-latest",
            f"--output={results_file}",
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            print("✅ Query executed successfully")

            # Also create a symlink to latest results
            latest_link = self.results_dir / "latest-results.sarif"
            if latest_link.exists():
                latest_link.unlink()
            latest_link.symlink_to(results_file.name)

            return results_file
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to run query:")
            print(f"Command: {' '.join(cmd)}")
            print(f"Error: {e.stderr}")
            return None

    def parse_results(self, results_file):
        """Parse SARIF results and extract LLM taint flows"""
        try:
            with open(results_file, "r") as f:
                sarif_data = json.load(f)

            findings = []
            for run in sarif_data.get("runs", []):
                for result in run.get("results", []):
                    rule_id = result.get("ruleId", "")
                    message = result.get("message", {}).get("text", "")

                    # Extract locations
                    locations = []
                    for location in result.get("locations", []):
                        phys_loc = location.get("physicalLocation", {})
                        artifact_loc = phys_loc.get("artifactLocation", {})
                        region = phys_loc.get("region", {})

                        locations.append(
                            {
                                "file": artifact_loc.get("uri", ""),
                                "line": region.get("startLine", 0),
                                "column": region.get("startColumn", 0),
                            }
                        )

                    # Extract code flows (taint paths)
                    code_flows = []
                    for flow in result.get("codeFlows", []):
                        for thread_flow in flow.get("threadFlows", []):
                            path = []
                            for step in thread_flow.get("locations", []):
                                step_loc = step.get("location", {}).get("physicalLocation", {})
                                step_artifact = step_loc.get("artifactLocation", {})
                                step_region = step_loc.get("region", {})

                                path.append(
                                    {
                                        "file": step_artifact.get("uri", ""),
                                        "line": step_region.get("startLine", 0),
                                        "message": step.get("location", {})
                                        .get("message", {})
                                        .get("text", ""),
                                    }
                                )
                            code_flows.append(path)

                    findings.append(
                        {
                            "rule_id": rule_id,
                            "message": message,
                            "locations": locations,
                            "code_flows": code_flows,
                        }
                    )

            return findings
        except Exception as e:
            print(f"❌ Failed to parse results: {e}")
            return []

    def analyze(self, source_path, output_file=None):
        source_path = "/Users/ferdi/Documents/CodeQL-Analyst/test"
        """Run complete analysis on source code"""

        # source_path = Path("/Users/ferdi/Documents/llm-code-assist") # analyzer.script_dir / "test" / "example_user_file.py"
        print(f"🚀 Starting LLM taint analysis on: {source_path}")

        # Check installation
        if not self.check_installation():
            return False

        # Create database
        db_path = self.create_database(source_path)
        if not db_path:
            return False

        # Run query
        results_file = self.run_query(db_path)
        if not results_file:
            return False

        # Parse and display results
        findings = self.parse_results(results_file)
        self.display_results(findings)

        # Save results to JSON if requested
        if output_file:
            self.save_json_results(findings, output_file)

        return True

    def display_results(self, findings):
        """Display analysis results in a readable format"""
        if not findings:
            print("✅ No LLM taint flows detected!")
            return

        print(f"\n🔍 Found {len(findings)} LLM taint flow(s):")
        print("=" * 60)

        for i, finding in enumerate(findings, 1):
            print(f"\n--- Finding #{i} ---")
            print(f"Rule: {finding['rule_id']}")
            print(f"Message: {finding['message']}")

            if finding["locations"]:
                loc = finding["locations"][0]
                print(f"Location: {loc['file']}:{loc['line']}")

            # Display taint flow path
            if finding["code_flows"]:
                print("\n🔄 Taint Flow Path:")
                for j, flow in enumerate(finding["code_flows"]):
                    for k, step in enumerate(flow):
                        print(f"  {k+1}. {step['file']}:{step['line']} - {step['message']}")

    def save_json_results(self, findings, output_file):
        """Save results to JSON file"""
        try:
            with open(output_file, "w") as f:
                json.dump(
                    {
                        "timestamp": datetime.now().isoformat(),
                        "findings_count": len(findings),
                        "findings": findings,
                    },
                    f,
                    indent=2,
                )
            print(f"💾 Results saved to: {output_file}")
        except Exception as e:
            print(f"❌ Failed to save results: {e}")


def main():
    parser = argparse.ArgumentParser(description="CodeQL LLM Taint Analysis Tool")
    parser.add_argument("source_path", nargs="?", help="Path to source code to analyze")
    parser.add_argument("--output", "-o", help="Output file for JSON results")
    parser.add_argument("--test", action="store_true", help="Run test analysis")
    parser.add_argument("--codeql-path", help="Path to CodeQL CLI binary")

    args = parser.parse_args()

    analyzer = CodeQLAnalyzer(args.codeql_path)

    if args.test:
        # Test with example file
        # test_file = Path("/Users/ferdi/Documents/llm-code-assist")
        test_file = analyzer.script_dir / "test" / "example_user_file.py"
        if test_file.exists():
            print("🧪 Running test analysis...")
            analyzer.analyze(str(test_file.parent), args.output)
        else:
            print("❌ Test file not found. Please check test/example_user_file.py")
        return

    if not args.source_path:
        print("❌ Please provide a source path to analyze")
        parser.print_help()
        return

    if not os.path.exists(args.source_path):
        print(f"❌ Source path does not exist: {args.source_path}")
        return

    analyzer.analyze(args.source_path, args.output)


if __name__ == "__main__":
    main()
