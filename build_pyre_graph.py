import json
import os
from typing import Dict, Set, Tuple, Optional
import networkx as nx
import matplotlib.pyplot as plt


class RepoGraph:
    """Builds and visualizes dependency graphs from Pyre JSONL output."""
    
    def __init__(self, jsonl_path: str, repo_path: str):
        """Initialize with path to Pyre JSONL file and repository root path."""
        self.jsonl_path = jsonl_path
        self.repo_path = os.path.abspath(repo_path)
        self.graph = nx.DiGraph()
        self.models = {}  # callable -> filename mapping
        self.repo_callables = set()  # callables that are in the repository
        
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
        return abs_filename.startswith(self.repo_path)
    
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
                filename = data.get('path')
                
                if callable_name:
                    # Store the mapping regardless of whether it's in repo
                    if filename:
                        self.models[callable_name] = filename
                    
                    # Check if this callable is in the repository
                    if self._is_repo_file(filename):
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
        
        if not os.path.exists(self.repo_path):
            raise FileNotFoundError(f"Repository path not found: {self.repo_path}")
        
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
    
    def plot_graph(self, figsize: Tuple[int, int] = (12, 8), 
                   node_color: str = "lightblue", node_size: int = 1200) -> None:
        """Plot the dependency graph."""
        if not self.graph.nodes():
            print("No nodes to plot. Graph is empty.")
            return
        
        plt.figure(figsize=figsize)
        pos = nx.spring_layout(self.graph, k=0.5, iterations=50)
        
        # Separate repo nodes from external nodes for different styling
        repo_nodes = [node for node in self.graph.nodes() if node in self.repo_callables]
        external_nodes = [node for node in self.graph.nodes() if node not in self.repo_callables]
        
        # Draw repo nodes in one color, external nodes in another
        if repo_nodes:
            nx.draw_networkx_nodes(self.graph, pos, nodelist=repo_nodes, 
                                  node_color=node_color, node_size=node_size, alpha=0.9)
        if external_nodes:
            nx.draw_networkx_nodes(self.graph, pos, nodelist=external_nodes, 
                                  node_color="lightcoral", node_size=node_size//2, alpha=0.7)
        
        nx.draw_networkx_edges(self.graph, pos, arrowstyle="->", 
                              arrowsize=15, edge_color="gray")
        nx.draw_networkx_labels(self.graph, pos, font_size=8, 
                               font_family="sans-serif")
        
        plt.title("Repository Dependency Graph")
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


def main():
    """Example usage of RepoGraph."""
    jsonl_path = '/Users/ferdi/Documents/agent-copilot/pyre_config/here13/taint-output.json'
    repo_path = '/Users/ferdi/Documents/agent-copilot/testbed/code_repos/try'

    try:
        repo_graph = RepoGraph(jsonl_path, repo_path)
        graph = repo_graph.build_graph()
        
        # Display repository callables
        repo_callables = repo_graph.get_repo_callables()
        print("Repository Callables:")
        for callable_name in sorted(repo_callables):
            print(f"  {callable_name}")
        
        # Display statistics
        stats = repo_graph.get_stats()
        print("\nGraph Statistics:")
        for key, value in stats.items():
            print(f"  {key.replace('_', ' ').title()}: {value}")
        
        # Show adjacency list
        adjacency_list = repo_graph.get_adjacency_list()
        if adjacency_list:
            print("\nAdjacency List (caller -> [callees]):")
            for caller, callees in adjacency_list.items():
                print(f"  {caller} -> {callees}")
        
        # Plot the graph
        repo_graph.plot_graph()
        
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Please provide valid paths to your Pyre JSONL output and repository.")


if __name__ == "__main__":
    main()
