import shutil
import subprocess
import sys
import json
import os
from typing import Dict, Set, Tuple, Optional
import networkx as nx
import matplotlib.pyplot as plt

from agent_copilot.logging_config import setup_logging
logger = setup_logging()


def path_to_id(path):
    return ".".join(path.split("/")[-3:])


class StaticRepoGraph:
    """Builds and visualizes static analysis graphs from Pyre JSONL output."""
    
    def __init__(self, repo_root: str):
        """Initialize with path to Pyre JSONL file and repository root path."""
        # Paths.
        self.repo_root = os.path.abspath(repo_root)
        cur_dir = os.path.dirname(os.path.abspath(__file__))
        self.pyre_folder = os.path.join(cur_dir, "pyre_static_analysis")
        self.results_folder = os.path.join(self.pyre_folder, "_results", path_to_id(repo_root))
        self.jsonl_path = os.path.join(self.results_folder, "taint-output.json")
        
        # Copy over models and stubs if not in repo.
        # HACK: This is because I couldn't figure out how to do this properly.
        if not os.path.exists(os.path.join(self.pyre_folder, "models_and_stubs", "taint")):
            shutil.copy(os.path.join(self.pyre_folder, "models_and_stubs"), self.repo_root)

        # Build graph directly upon construction.
        self.graph = nx.DiGraph()
        self.models = {}  # callable -> filename mapping
        self.repo_callables = set()  # callables that are in the repository
        self.run_pyre()
        self.build_graph()

        
    def _is_repo_file(self, filename: str, path: str = None) -> bool:
        """Check if filename or path is part of the repository."""
        # If we have a path field, use it when filename is "*"
        file_to_check = path if (filename == "*" and path) else filename
        
        if not file_to_check:
            return False
        
        # Case 3: No valid filename/path
        if file_to_check == "*":
            return False
            
        # Case 2: Relative path - assume it's in repo
        if not os.path.isabs(file_to_check):
            return True
            
        # Case 1: Absolute path - check if it's inside repo_path
        abs_filename = os.path.abspath(file_to_check)
        return abs_filename.startswith(self.repo_root)
    

    def _extract_models_and_repo_callables(self) -> None:
        """Extract model information and identify repository callables from JSONL file."""
        with open(self.jsonl_path, 'r') as file:
            for line in file:
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                
                data = entry.get('data', {})
                callable_name = data.get('callable')
                filename = data.get('filename')  # Note: using 'filename' field for consistency
                path = data.get('path')          # Also get 'path' field as backup
                
                if callable_name:
                    # Store the mapping regardless of whether it's in repo
                    # Use path if available, otherwise use filename
                    file_to_store = path if path else filename
                    if file_to_store:
                        self.models[callable_name] = file_to_store
                    
                    # Check if this callable is in the repository using both filename and path
                    if self._is_repo_file(filename, path):
                        self.repo_callables.add(callable_name)
                        # Add the node to the graph even if it has no edges
                        self.graph.add_node(callable_name)    

    def _add_model_edges(self) -> None:
        """Add edges from model call relationships."""
        with open(self.jsonl_path, 'r') as file:
            for line in file:
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                
                if entry.get('kind') != 'model':
                    continue
                
                data = entry['data']
                caller = data.get('callable')
                
                if not caller or caller not in self.repo_callables:
                    continue
                
                # Extract call relationships from sinks
                for sink in data.get('sinks', []):
                    for taint in sink.get('taint', []):
                        call_info = taint.get('call')
                        if call_info:
                            for callee in call_info.get('resolves_to', []):
                                self._add_edge_if_valid(caller, callee)
    
    def _add_issue_edges(self) -> None:
        """Add edges from issue data."""
        with open(self.jsonl_path, 'r') as file:
            for line in file:
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                
                if entry.get('kind') != 'issue':
                    continue
                
                data = entry.get('data', {})
                caller = data.get('callable')
                sink_handle = data.get('sink_handle')
                
                if caller and isinstance(sink_handle, dict):
                    callee = sink_handle.get('callee')
                    if callee:
                        self._add_edge_if_valid(caller, callee)
    

    def _add_edge_if_valid(self, caller: str, callee: str) -> None:
        """Add edge if at least one node is from repository."""
        # Add edge if either caller or callee is in the repository
        # This ensures we capture all interactions involving repo code
        if caller in self.repo_callables or callee in self.repo_callables:
            self.graph.add_edge(caller, callee)
            
            # Also add individual nodes to ensure they're in the graph
            if caller in self.repo_callables:
                self.graph.add_node(caller)
            if callee in self.repo_callables:
                self.graph.add_node(callee)
    

    def build_graph(self) -> nx.DiGraph:
        """Build the complete dependency graph."""
        if not os.path.exists(self.jsonl_path):
            raise FileNotFoundError(f"JSONL file not found: {self.jsonl_path}")
        
        if not os.path.exists(self.repo_root):
            raise FileNotFoundError(f"Repository path not found: {self.repo_root}")
        
        self._extract_models_and_repo_callables()
        self._add_model_edges()
        self._add_issue_edges()
        
        return self.graph
    

    def get_repo_callables(self) -> Set[str]:
        """Get all callables that are part of the repository."""
        return self.repo_callables.copy()
    

    def get_adjacency_list(self) -> Dict[str, list]:
        """Get adjacency list representation of the graph."""
        return {node: sorted(list(self.graph.successors(node))) 
                for node in self.graph.nodes() if self.graph.out_degree(node) > 0}
    
    
    def plot_graph(self, label_nodes=True) -> None:
        """Plot the dependency graph."""
        if not self.graph.nodes():
            logger.error("No nodes to plot. Graph is empty.")
            return
        
        plt.figure(figsize=(8,6))
        pos = nx.spring_layout(self.graph, k=0.5, iterations=50)
                
        # Draw repo nodes in one color, external nodes in another
        nx.draw_networkx_nodes(self.graph, pos, nodelist=self.graph.nodes()) 
        
        nx.draw_networkx_edges(self.graph, pos, arrowsize=20)
        if label_nodes:
            nx.draw_networkx_labels(self.graph, pos)
        
        # plt.title("Repository Dependency Graph")
        plt.axis("off")
        plt.tight_layout()
        plt.show()
    

    def get_stats(self) -> Dict[str, int]:
        """Get basic statistics about the graph."""
        return {
            "total_nodes": self.graph.number_of_nodes(),
            "repo_nodes": len(self.repo_callables),
            "external_nodes": self.graph.number_of_nodes() - len(self.repo_callables),
            "edges": self.graph.number_of_edges(),
            "strongly_connected_components": len(list(nx.strongly_connected_components(self.graph))),
            "weakly_connected_components": len(list(nx.weakly_connected_components(self.graph)))
        }


    def run_pyre(self):
        if os.path.exists(self.jsonl_path):
            # NOTE: Need to disable once we run on repos where users update code.
            return

        # 1. Make config
        config = {
            "site_package_search_strategy": "none",
            "source_directories": [
                self.repo_root
            ],
            "search_path": [
                self.repo_root
            ],
            "taint_models_path": [
                os.path.join(self.repo_root, "taint")
            ],
            "exclude": [
                ".*/build/.*",
                ".*/venv/.*",
                "*miniconda*"
            ],
            "strict": True
        }

        with open(os.path.join(self.pyre_folder, ".pyre_configuration"), "w") as f:
            json.dump(config, f, indent=2)

        # 2. Run Pyre
        logger.info(f"Running static analysis of {self.repo_root}")
        os.chdir(self.pyre_folder)
        command = ["pyre", "analyze", "--save-results-to", self.results_folder]
        try:
            subprocess.run(command, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            logger.error("Static analysis failed:")
            print(e.stderr)
            sys.exit(1)
        logger.info("Finished static analysis")


if __name__ == "__main__":
    s = StaticRepoGraph("/Users/ferdi/Documents/agent-copilot/testbed/code_repos/try")
    s.plot_graph()
