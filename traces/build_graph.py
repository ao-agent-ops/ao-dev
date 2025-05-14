from collections import defaultdict
from difflib import SequenceMatcher
from enum import Enum
import json
import os
import re
import time
from matplotlib.patches import Patch
import networkx as nx
import matplotlib.pyplot as plt
import concurrent.futures
from main import setup_logging

logger = setup_logging()


class GraphType(Enum):
    CODE_GEN = "code_gen"
    EMPTY = "empty"


class CallGraph:
    """
    Dependency tree of LLM calls, with input and output nodes.
    E.g.: input <-- LLM_call_1 <-- LLM_call_2 <-- output

    CallGraph also contains eval data of graph nodes (e.g., pass/fail 
    for unit tests).

    `trace_path` can be an exact path, or:
     - 'fundraising_crm latest'
    """

    def __init__(self, trace_path):

        # 1. If path doesn't exist, assume it's a trace name.
        self.trace_path = trace_path
        if not os.path.exists(trace_path):
            self.trace_path = get_trace_path(trace_path)

        self.G = None
        self.graph_type = GraphType.EMPTY

        self.terminal_nodes = []

        # Attributes for code-gen.
        # TODO


    def from_codegen_log(self):
        """
        Parses out the call lineage of how functions are generated. 
        For each test, it also parses out what functions that test 
        called.
        """
        self.graph_type = GraphType.CODE_GEN
        self.G = nx.DiGraph()
        
        # 2. Read file and init nodes.
        start = time.time()
        with open(os.path.join(self.trace_path, "fundraising_crm_traj.jsonl"), "r") as f:
            llm_calls = f.readlines()
        
        # Node 0 is the input spec.
        self.G.add_node(0, 
                system_mg="N/A",
                llm_in="N/A", 
                llm_out="N/A", 
                timestamp="N/A", 
                cache_key="root_spec_0_user")

        # Add nodes from trace file.
        for id, llm_call in enumerate(llm_calls):
            call_dict = json.loads(llm_call)
            self.G.add_node(id+1, 
                            system_mg=call_dict["system_msg"],
                            llm_in=call_dict["prompt"], 
                            llm_out=call_dict["output"], 
                            timestamp=call_dict["timestamp"], 
                            cache_key=call_dict["cache_key"])
        logger.debug(f"Insert nodes: {time.time() - start}")

        # 3. Insert edges (build dependency lineage).
        start = time.time()
        self._insert_edges_hardcoded()

        self.terminal_nodes = []
        for node in self.G.nodes:
            if self.G.degree(node) == 1:
                self.terminal_nodes.append(node)
        logger.debug(f"Insert edges: {time.time() - start}")


    def get_test_lineage(self, test_name):
        """
        test_name must have format like: `database/test_db_operations.py`

        `test_function_calls.json` has the following format:
        {
          "database/test_db_operations.py": ["database.db_operations"]
        }
        """
        # Get all functions called by the test case.
        with open(os.path.join(self.trace_path, "test_function_calls.json"), "r") as f:
            called_functions_dict = json.load(f)
        called_functions = called_functions_dict[test_name]

        # Loop through terminal nodes and see which ones generated called functions.
        test_terminal_nodes = []
        test_added = False # test node will be added many times bc per class ... maybe better way to do this?
        for t in self.terminal_nodes:
            cache_key = self.G.nodes[t]["cache_key"]

            if "test" in cache_key:
                transformed_cache_key = self._test_id_from_cache_key(cache_key)
                if not test_added and transformed_cache_key in called_functions:
                    test_terminal_nodes.append(t)
                    test_added = True # TODO: We have several entries for same test ... leave for now but need to address
            else:
                transformed_cache_key = self._function_id_from_cache_key(cache_key)
                if transformed_cache_key in called_functions:
                    test_terminal_nodes.append(t)

        # Insert lineage of each called function.
        test_lineage = nx.DiGraph()
        for src in test_terminal_nodes:
            for u, v in nx.dfs_edges(self.G, source=src):
                test_lineage.add_edge(u, v)


        # HACK: Just for visualization purposes, we abuse this function and don't only insert the DFS 
        # tree but also add further (unnecessary) edges.
        # TODO: Delete this part.
        for u, v in [(15, 0), (2, 0)]:
            test_lineage.add_edge(u, v)

        return test_lineage


    def visualize(self):
        plt.figure(figsize=(7, 3.5))

        # Categorize nodes for plotting.
        root_node = [0]
        normal_nodes = []
        exit_nodes = []
        for node in self.G.nodes:
            if self.G.degree(node) == 0:
                # TODO: There are "stray test reviews" (i.e., review -> {missing fix} -> review).
                # We will just pretend they aren't there.
                # print("Ignoring", self.G.nodes[node]["cache_key"])
                continue
            elif self.G.degree(node) == 1:
                exit_nodes.append(node)
            else:
                normal_nodes.append(node)

        # Plotting layout (spread nodes out)
        pos = nx.spring_layout(self.G, k=0.06, iterations=50, seed=42)
        
        # Normal nodes.
        nx.draw_networkx_nodes(self.G,
                            pos,
                            nodelist=normal_nodes,
                            node_size=50,
                            label="LLM calls")

        # Root node.
        nx.draw_networkx_nodes(self.G,
                            pos,
                            nodelist=root_node,
                            node_size=150,
                            node_color='red',
                            label="User's design doc")
        
        # Terminal nodes.
        nx.draw_networkx_nodes(self.G,
                            pos,
                            nodelist=exit_nodes,
                            node_size=70,
                            node_color="limegreen",
                            label="Terminal LLM call")


        legend_handles = [
            Patch(color='red', label="User's design doc"),
            Patch(color='limegreen', label="Terminal LLM call"),
            Patch(color='tab:blue', label="LLM calls")
        ]

        plt.title("LLM Call Dependency Graph")
        plt.legend(handles=legend_handles, loc='upper left')
        nx.draw_networkx_edges(self.G, pos)
        # plt.legend(loc="lower right")
        plt.show()


    # def _test_id_from_cache_key(self, cache_key):
    #     parts = cache_key.split('.')
    #     if len(parts) < 4:
    #         raise ValueError("We're assuming a string like this:" \
    #         "{prefix}.{module}.{file}.{suffix with dot, e.g. abc_sonnet-3.7_abc}")

    #     # Assume format: {prefix}.{folder}.{module}.{suffix}
    #     folder = parts[-4]
    #     module = parts[-3]

    #     filename = f"test_{module}.py"
    #     return f"{folder}/{filename}"

    def _test_id_from_cache_key(self, cache_key):
        parts = cache_key.split('.')
        if len(parts) < 4:
            raise ValueError("Expected format: {prefix}.{module}.{file_with_suffix}")

        module = parts[-4]
        file_with_suffix = parts[-3]

        # Split by underscore and keep parts until we hit the first digit-starting part
        file_parts = []
        for part in file_with_suffix.split('_'):
            if re.match(r'^\d', part):  # starts with a digit, suffix begins
                break
            file_parts.append(part)

        file = '_'.join(file_parts)
        return f"{module}.test_{file}"


    def _function_id_from_cache_key(self, cache_key):
        parts = cache_key.split('.')
        if len(parts) < 3:
            raise ValueError("Expected format: {prefix}.{module}.{file_with_suffix}")

        module = parts[-3]
        file_with_suffix = parts[-2]

        # Split by underscore and keep parts until we hit the first digit-starting part
        file_parts = []
        for part in file_with_suffix.split('_'):
            if re.match(r'^\d', part):  # starts with a digit, suffix begins
                break
            file_parts.append(part)

        file = '_'.join(file_parts)
        return f"{module}.{file}"


    def _insert_edges_lcs(self, match_threshold=100):
        for n_in in self.G.nodes:
            longest = 0
            n_out_longest = -1
            for n_out in self.G.nodes:
                in_text = self.G.nodes[n_in]["llm_in"]
                out_text = self.G.nodes[n_out]["llm_out"]

                # TODO: Just assume there's only one or 0 edges. 
                length = find_longest_match(in_text, out_text)
                if length > longest:
                    longest = length
                    n_out_longest = n_out

            if longest > match_threshold:
                self.G.add_edge(n_in, n_out_longest)


    def _insert_edges_lcs_parallel(self, match_threshold=100):
        # 1. Determine which edges to add in parallel.
        node_attrs = {node: {"llm_in": self.G.nodes[node].get("llm_in", ""),
                            "llm_out": self.G.nodes[node].get("llm_out", "")}
                    for node in self.G.nodes}

        args_list = [(n1, n2, node_attrs[n1], node_attrs[n2], match_threshold)
                    for n1 in node_attrs for n2 in node_attrs]
        with concurrent.futures.ProcessPoolExecutor() as executor:
            results = executor.map(compare_nodes, args_list)

        # 2. Add edges from results
        for result in results:
            if result:
                n_in, n_out, score = result
                self.G.add_edge(n_in, n_out, score=score)


    def _insert_edges_hardcoded(self):
        # TODO BUG: Unexpected terminals:
        # review should be last
        # method_test_transpiling_fix_fundraising_crm_tree_src.app.app.FlaskApp_9_sonnet3.7-nothink  terminal
        # Odd number should be last 
        # file_transpiler_transpilation_fundraising_crm_tree_src.database.db_operations_34_sonnet3.7-nothink
        # file_transpiler_transpilation_fundraising_crm_tree_src.app.routes_34_sonnet3.7-nothink


        # 1. Connect code transpile nodes.
        self._connect_adjacent_cache_keys(node_type="file_planner_analysis", dependent_node_type="file_planner_iterate")
        self._connect_adjacent_cache_keys(node_type="file_planner_iterate", dependent_node_type="file_transpiler_analysis")
        self._connect_adjacent_cache_keys(node_type="file_transpiler_analysis", dependent_node_type="file_transpiler_transpilation")
        self._connect_adjacent_cache_keys(node_type="file_transpiler_transpilation", dependent_node_type=None)

        # 2. Connect test transpile nodes.
        self._connect_adjacent_cache_keys(node_type="class_test_spec_gen_unit", dependent_node_type="class_test_spec_gen_integration")
        self._connect_adjacent_cache_keys(node_type="class_test_spec_gen_integration", dependent_node_type="method_test_transpiling_gen")
        self._connect_adjacent_cache_keys(node_type="method_test_transpiling_gen", dependent_node_type="method_test_transpiling_review")
        self._interleave_cache_keys(node_type="method_test_transpiling_review", dependent_node_type="method_test_transpiling_fix")

        # self._connect_node_types(node_type="class_test_spec_gen_unit", dependent_node_type="class_test_spec_gen_integration")
        # self._connect_node_types(node_type="class_test_spec_gen_unit", dependent_node_type="method_test_transpiling_gen")

        # 3. Connect to root spec.
        self._connect_to_root(dependent_node_type="file_planner_analysis")
        self._connect_to_root(dependent_node_type="class_test_spec_gen_unit")
        # self._connect_to_root(dependent_node_type="class_test_spec_gen_integration")

        # 4. Connect test cases to planner.
        self.delete_unconnected() # TODO: Sometimes there's an extra review (without fix before).
        self._connect_node_types(node_type="method_test_transpiling_review", dependent_node_type="file_planner_analysis", test_and_impl=True)

    
    def delete_unconnected(self):
        isolated_nodes = list(nx.isolates(self.G))
        self.G.remove_nodes_from(isolated_nodes)



    def _group_nodes_by_cache_key(self, node_type):
        """
        Groups nodes by (middle, suffix): their numeric index and node_id.
        Returns dict { (middle, suffix): [(x, node_id), ...] }
        """
        # Regex: match node_type prefix, capture middle, number, and suffix
        pattern = re.compile(rf"^{re.escape(node_type)}_(.*?_)(\d+)(_.*)$")
        grouped = defaultdict(list)

        for node_id in self.G.nodes:
            cache_key = self.G.nodes[node_id].get("cache_key", "")
            match = pattern.match(cache_key)
            if not match:
                continue

            middle, num_str, suffix = match.groups()
            grouped[(middle, suffix)].append((int(num_str), node_id))

        return grouped


    def _group_test_and_impl_nodes_by_cache_key(self, node_type):
        """
        Groups nodes by a canonical key (module + file, without any class suffix).
        Returns: dict { key: [(index, node_id), ...] }
        """
        # match <node_type>_<middle>_<index>_<suffix>
        pattern = re.compile(rf"^{re.escape(node_type)}_(.*?_)(\d+)(_.*)$")
        grouped = defaultdict(list)

        for node_id in self.G.nodes:
            cache_key = self.G.nodes[node_id].get("cache_key", "")
            m = pattern.match(cache_key)
            if not m:
                continue

            middle_with_underscore, num_str, _suffix = m.groups()

            # 1) strip the trailing underscore
            middle = middle_with_underscore.rstrip('_')

            # 2) split on '.' and drop a final class name if it starts with uppercase
            parts = middle.split('.')
            if parts and parts[-1] and parts[-1][0].isupper():
                parts.pop()

            # recombine into our canonical key
            canonical_key = '.'.join(parts)

            grouped[canonical_key].append((int(num_str), node_id))

        return grouped


    def _connect_adjacent_cache_keys(self, node_type, dependent_node_type=None):
        """
        Connects nodes of node_type by adding edges x → x-1,
        and if dependent_node_type is provided, adds an edge from the first
        node of dependent_node_type to the last node of node_type,
        for each shared (middle, suffix) group.
        """
        # Intra-type connections
        primary_map = self._group_nodes_by_cache_key(node_type)
        for key, entries in primary_map.items():
            entries.sort()
            nodes_by_x = {x: nid for x, nid in entries}
            for x, node_id in nodes_by_x.items():
                prev_x = x - 1
                if prev_x in nodes_by_x:
                    self.G.add_edge(node_id, nodes_by_x[prev_x])

        # Cross-type connection (first dependent → last primary)
        if dependent_node_type:
            self._connect_node_types(node_type, dependent_node_type)


    def _interleave_cache_keys(self, node_type, dependent_node_type):
        """
        Connects two node types in an interleaved zig-zag pattern:
        For each version x in their shared groups:
          dependent[x] → node_type[x]
          node_type[x+1] → dependent[x]
          dependent[x+1] → node_type[x+1]
        """
        map_dep = self._group_nodes_by_cache_key(dependent_node_type)
        map_main = self._group_nodes_by_cache_key(node_type)

        # Only process groups present in both types
        for key in map_dep.keys() & map_main.keys():
            dep_entries = {x: nid for x, nid in map_dep[key]}
            main_entries = {x: nid for x, nid in map_main[key]}
            all_versions = sorted(set(dep_entries) | set(main_entries))

            for x in all_versions:
                dep_cur = dep_entries.get(x)
                main_cur = main_entries.get(x)
                dep_next = dep_entries.get(x + 1)
                main_next = main_entries.get(x + 1)

                # dependent[x] → main[x]
                if dep_cur and main_cur:
                    self.G.add_edge(dep_cur, main_cur)
                # main[x+1] → dependent[x]
                if main_next and dep_cur:
                    self.G.add_edge(main_next, dep_cur)
                # dependent[x+1] → main[x+1]
                if dep_next and main_next:
                    self.G.add_edge(dep_next, main_next)


    def _connect_node_types(self, node_type, dependent_node_type, test_and_impl=False):
        """
        For each shared (middle, suffix) group between node_type and dependent_node_type,
        adds an edge from the first node of dependent_node_type to the last node of node_type.
        """
        if test_and_impl:
            primary_map = self._group_test_and_impl_nodes_by_cache_key(node_type)
            dep_map = self._group_test_and_impl_nodes_by_cache_key(dependent_node_type)
        else:
            primary_map = self._group_nodes_by_cache_key(node_type)
            dep_map = self._group_nodes_by_cache_key(dependent_node_type)

        # For keys present in both maps, connect first dependent → last primary
        for key in primary_map.keys() & dep_map.keys():
            entries = primary_map[key]
            dep_entries = dep_map[key]
            _, last_primary = max(entries)
            _, first_dep = min(dep_entries)
            self.G.add_edge(first_dep, last_primary)


    def _connect_to_root(self, dependent_node_type, root_id=0):
        """
        For each shared (middle, suffix) group between node_type and dependent_node_type,
        adds an edge from the first node of dependent_node_type to the last node of node_type.
        """
        dep_map = self._group_nodes_by_cache_key(dependent_node_type)

        # For keys present in both maps, connect first dependent → last primary
        for key in dep_map.keys():
            dep_entries = dep_map[key]
            _, first_dep = min(dep_entries)
            self.G.add_edge(first_dep, root_id)

# =========================================================
# Helpers
# =========================================================
def compare_nodes(args):
    n_in, n_out, attrs_in, attrs_out, threshold = args
    if n_in == n_out:
        return None
    score = find_longest_match(attrs_in["llm_in"], attrs_out["llm_out"])
    if score > threshold:
        return (n_in, n_out, score)
    return None


def get_trace_path(trace_name):
    """
    Possible trace_names: 
     - 'fundraising_crm latest'
    """
    cur_dir = os.path.dirname(__file__)
    if trace_name == 'fundraising_crm latest':
        prefix = "fundraising_crm_"
        code_gen_dir = os.path.join(cur_dir, "code_gen")

        most_recent = max([
            d for d in os.listdir(code_gen_dir)
            if os.path.isdir(os.path.join(code_gen_dir, d)) and re.match(rf"{prefix}\d{{2}}_\d{{2}}$", d)
        ])

        assert most_recent, "No matching trace dir present"
        fundraising_crm_dir = os.path.join(cur_dir, "code_gen", most_recent)
        return fundraising_crm_dir
    else:
        raise ValueError(f"Trace name '{trace_name}' is not a recognized.")


def normalize_tokens(text):
    lines = [ln.lstrip() for ln in text.splitlines()]
    flat = " ".join(lines).lower().strip()
    return re.findall(r"\w+|\S", flat)


def find_longest_match(string_a, string_b):
    a_tok = normalize_tokens(string_a)
    b_tok = normalize_tokens(string_b)
    sm = SequenceMatcher(None, a_tok, b_tok)

    a = [block.size for block in sm.get_matching_blocks()]
    b = [block for block in sm.get_matching_blocks()]

    # a_str = a_tok[b[4].a:b[4].a+100]
    # b_str = b_tok[b[4].b:b[4].b+100]

    max_match = max([block.size for block in sm.get_matching_blocks()])
    # if max_match > 100:
    #     print()
    return max_match


def plot_lineage_graph(lineage):
    plt.figure(figsize=(7, 3.5))

    # your layout
    pos = nx.kamada_kawai_layout(lineage)

    # the nodes you want to highlight
    big_red   = {0}
    small_green = {284, 264, 170, 146}

    # build parallel lists of colors and sizes
    colors = []
    sizes  = []
    for n in lineage.nodes():
        if n in big_red:
            colors.append('red')
            sizes.append(200)       # big
        elif n in small_green:
            colors.append('limegreen')
            sizes.append(100)       # medium
        else:
            colors.append('tab:blue')
            sizes.append(50)        # default

    # draw
    nx.draw_networkx(
        lineage,
        pos,
        node_color=colors,
        node_size=sizes,
        with_labels=False
    )

    legend_handles = [
        Patch(color='red', label="User's design doc"),
        Patch(color='limegreen', label="Terminal LLM call"),
        Patch(color='tab:blue', label="LLM calls")
    ]

    plt.title("LLM Call Dependency Graph")
    plt.legend(handles=legend_handles, loc='best')
    # plt.title("Dependency graph")
    plt.show()



if __name__ == "__main__":
    cg = CallGraph("fundraising_crm latest")
    cg.from_codegen_log()
    # cg.visualize()

    lineage = cg.get_test_lineage("backend_services/test_agent_service.py")
    plot_lineage_graph(lineage)
