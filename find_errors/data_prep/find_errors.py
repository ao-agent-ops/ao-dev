from prompts import *
import json
from amadou_parse_tags import parse_out_tag

# TODO: Automatoically do from lineage graph.


# Relevant cache keys.
cache_keys = [
    "file_planner_analysis_fundraising_crm_tree_src.app.routes_0_sonnet3.7-nothink",
    "file_planner_analysis_fundraising_crm_tree_src.app.routes_1_sonnet3.7-nothink",
    "file_planner_iterate_fundraising_crm_tree_src.app.routes_0_sonnet3.7-nothink",
    "file_planner_iterate_fundraising_crm_tree_src.app.routes_1_sonnet3.7-nothink",
    "file_planner_iterate_fundraising_crm_tree_src.app.routes_2_sonnet3.7-nothink",
    "file_planner_iterate_fundraising_crm_tree_src.app.routes_3_sonnet3.7-nothink",
    "file_planner_iterate_fundraising_crm_tree_src.app.routes_4_sonnet3.7-nothink",
    "file_planner_iterate_fundraising_crm_tree_src.app.routes_5_sonnet3.7-nothink",
    "file_transpiler_analysis_fundraising_crm_tree_src.app.routes_0_sonnet3.7-nothink",
    "file_transpiler_analysis_fundraising_crm_tree_src.app.routes_1_sonnet3.7-nothink",
    "file_transpiler_transpilation_fundraising_crm_tree_src.app.routes_0_sonnet3.7-nothink",
    "file_transpiler_transpilation_fundraising_crm_tree_src.app.routes_1_sonnet3.7-nothink",
    "file_transpiler_transpilation_fundraising_crm_tree_src.app.routes_2_sonnet3.7-nothink",
    "file_transpiler_transpilation_fundraising_crm_tree_src.app.routes_3_sonnet3.7-nothink",
    "file_transpiler_transpilation_fundraising_crm_tree_src.app.routes_4_sonnet3.7-nothink",
    "file_transpiler_transpilation_fundraising_crm_tree_src.app.routes_5_sonnet3.7-nothink",
    "file_transpiler_transpilation_fundraising_crm_tree_src.app.routes_6_sonnet3.7-nothink",
    "file_transpiler_analysis_fundraising_crm_tree_src.app.routes_2_sonnet3.7-nothink",
    "file_transpiler_analysis_fundraising_crm_tree_src.app.routes_3_sonnet3.7-nothink",
    "file_transpiler_transpilation_fundraising_crm_tree_src.app.routes_7_sonnet3.7-nothink",
    "file_transpiler_transpilation_fundraising_crm_tree_src.app.routes_8_sonnet3.7-nothink",
    "file_transpiler_transpilation_fundraising_crm_tree_src.app.routes_9_sonnet3.7-nothink",
    "file_transpiler_transpilation_fundraising_crm_tree_src.app.routes_10_sonnet3.7-nothink",
    "file_transpiler_transpilation_fundraising_crm_tree_src.app.routes_11_sonnet3.7-nothink",
    "file_transpiler_transpilation_fundraising_crm_tree_src.app.routes_12_sonnet3.7-nothink",
    "file_transpiler_transpilation_fundraising_crm_tree_src.app.routes_13_sonnet3.7-nothink",
    "file_transpiler_analysis_fundraising_crm_tree_src.app.routes_4_sonnet3.7-nothink",
    "file_transpiler_analysis_fundraising_crm_tree_src.app.routes_5_sonnet3.7-nothink",
    "file_transpiler_transpilation_fundraising_crm_tree_src.app.routes_14_sonnet3.7-nothink",
    "file_transpiler_transpilation_fundraising_crm_tree_src.app.routes_15_sonnet3.7-nothink",
    "file_transpiler_transpilation_fundraising_crm_tree_src.app.routes_16_sonnet3.7-nothink",
    "file_transpiler_transpilation_fundraising_crm_tree_src.app.routes_17_sonnet3.7-nothink",
    "file_transpiler_transpilation_fundraising_crm_tree_src.app.routes_18_sonnet3.7-nothink",
    "file_transpiler_transpilation_fundraising_crm_tree_src.app.routes_19_sonnet3.7-nothink",
    "file_transpiler_transpilation_fundraising_crm_tree_src.app.routes_20_sonnet3.7-nothink",
    "file_transpiler_analysis_fundraising_crm_tree_src.app.routes_6_sonnet3.7-nothink",
    "file_transpiler_analysis_fundraising_crm_tree_src.app.routes_7_sonnet3.7-nothink",
    "file_transpiler_transpilation_fundraising_crm_tree_src.app.routes_21_sonnet3.7-nothink",
    "file_transpiler_transpilation_fundraising_crm_tree_src.app.routes_22_sonnet3.7-nothink",
    "file_transpiler_transpilation_fundraising_crm_tree_src.app.routes_23_sonnet3.7-nothink",
    "file_transpiler_transpilation_fundraising_crm_tree_src.app.routes_24_sonnet3.7-nothink",
    "file_transpiler_transpilation_fundraising_crm_tree_src.app.routes_25_sonnet3.7-nothink",
    "file_transpiler_transpilation_fundraising_crm_tree_src.app.routes_26_sonnet3.7-nothink",
    "file_transpiler_transpilation_fundraising_crm_tree_src.app.routes_27_sonnet3.7-nothink",
    "file_transpiler_analysis_fundraising_crm_tree_src.app.routes_8_sonnet3.7-nothink",
    "file_transpiler_analysis_fundraising_crm_tree_src.app.routes_9_sonnet3.7-nothink",
    "file_transpiler_transpilation_fundraising_crm_tree_src.app.routes_28_sonnet3.7-nothink",
    "file_transpiler_transpilation_fundraising_crm_tree_src.app.routes_29_sonnet3.7-nothink",
    "file_transpiler_transpilation_fundraising_crm_tree_src.app.routes_30_sonnet3.7-nothink",
    "file_transpiler_transpilation_fundraising_crm_tree_src.app.routes_31_sonnet3.7-nothink",
    "file_transpiler_transpilation_fundraising_crm_tree_src.app.routes_32_sonnet3.7-nothink",
    "file_transpiler_transpilation_fundraising_crm_tree_src.app.routes_33_sonnet3.7-nothink",
    "file_transpiler_transpilation_fundraising_crm_tree_src.app.routes_34_sonnet3.7-nothink"
]



# Read dicts.
with open("../traces/code_gen/fundraising_crm_05_09/fundraising_crm_traj.jsonl", "r") as f:
    lines = f.readlines()
dicts = [json.loads(l) for l in lines]


def pretty_display(raw_string: str):
    """
    Takes a raw string with escaped characters and prints it nicely formatted.
    """
    # Decode escaped sequences like \n, \t, \', etc.
    decoded = raw_string.encode().decode('unicode_escape')
    return decoded


def get_entry(cache_key, entry_type):
    for d in dicts:
        if cache_key == d["cache_key"]:
            return pretty_display(d[entry_type])


def get_string(cache_key, tag, entry_type="output"):
    full_entry = get_entry(cache_key, entry_type)
    relevant_part = parse_out_tag(full_entry, tag) 
    return relevant_part


def print_prompt():

    # Add analysis:
    analysis = get_string(cache_keys[0], "analysis", "output")
    prompt = instructions.format(analysis=analysis)
    print(prompt)
    step_ctr = 2

    # Add planning
    plan_itr = 0
    while f"file_planner_iterate_fundraising_crm_tree_src.app.routes_{plan_itr}_sonnet3.7-nothink" in cache_keys:
        cache_string = f"file_planner_iterate_fundraising_crm_tree_src.app.routes_{plan_itr}_sonnet3.7-nothink"
        plan = get_string(cache_string, "next_plan", "output")
        analysis = get_string(cache_string, "iteration_state", "output")
        prompt = plan_prompt.format(iter = step_ctr, plan=plan, analysis=analysis)
        print(prompt)

        step_ctr += 1
        plan_itr += 2

    # Add implementation.
    impl_iter = 0
    while True:
        cache_string_0 = f"file_transpiler_transpilation_fundraising_crm_tree_src.app.routes_{impl_iter}_sonnet3.7-nothink"
        cache_string_1 = f"file_transpiler_transpilation_fundraising_crm_tree_src.app.routes_{impl_iter+1}_sonnet3.7-nothink"

        if not cache_string_1 in cache_keys:
            break

        impl = get_string(cache_string_0, "transpilation", "output")
        review = get_string(cache_string_1, "review", "output")
        prompt = impl_prompt.format(iter=step_ctr, implementation=impl, review=review)
        print(prompt)

        step_ctr += 1
        impl_iter += 2



    # Analysis

# Spot the root cause. What was the earliest step from which the steps after could not recover anymore?
# 
# Step 1: Planner analysis: Analyzes the task and its difficulty. --- output
# Step 2 - xxx: Planner: Plans the implementation. Iteratively refines it --- output
# Step xxx - yyy: Output + review

# planner analysis: take output --> review



# They all have review fields. <review>
# Planner Analysis the second one
# Planner iter every second one --- they always seem to say that things are correct.

# Transpile analysis, the second one --- also always says they're correct
# Transpile the seocn one

# 

# transpile: Nimm direct den <review> von jedem zweiten.




# ANALYSIS:
# file_planner_analysis --- vlt auslassen? die sagen wie einfach und auch nen approach

# PLANNER:
# iteration_review --- iteration_review and dependency_analysis

# TRANSPILE: Just take the revuew part

# transpile analysis: difficulty and some fix stuff?
# file_transpiler_transpilation_ --> every second one. toml has transpilation_review and dependency_analysis




if __name__ == "__main__":
    print_prompt()


