import json
import os
import argparse
import logging
from utils import get_gpt_response_openai


logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(name)s -   %(message)s",
    datefmt="%m/%d/%Y %H:%M:%S",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


ignore_types = []
try:
    from gx_config import IGNORE_TYPES

    ignore_types = IGNORE_TYPES
except Exception:
    1


def check_cleansing(eval_system):
    all_folders = os.listdir("./data/")
    for folder in all_folders:
        if (
            os.path.isdir(f"./data/{folder}")
            and not folder.startswith("__")
            and not folder.startswith(".")
            and not folder.startswith("data")
        ):
            results_path = f"./data/{folder}/{eval_system}_results.txt"
            qa_path = f"./data/{folder}/{folder}_qa.jsonl"
            if not os.path.exists(results_path) or not os.path.exists(qa_path):
                logger.warning(f"Skipping folder {folder} because results or QA file is missing.")
                continue
            jsonlines = open(qa_path, "r").readlines()
            system_answers = []
            cur_qa_idx = 1
            cur_content = ""
            if eval_system == "ernie4":
                with open(results_path, "r") as f:
                    for line in f.readlines():
                        line = line.strip()
                        if line != "":
                            system_answers.append(line)
            else:
                with open(results_path, "r") as f:
                    for line in f.readlines():
                        line = line.strip()
                        if not line.startswith("1."):
                            pass
                        if line != "":
                            if line.startswith(f"{cur_qa_idx}."):
                                cur_content = line
                            elif line.startswith(f"{cur_qa_idx+1}."):
                                system_answers.append(cur_content)
                                cur_content = line
                                cur_qa_idx += 1
                            else:
                                cur_content += line
                system_answers.append(cur_content)

            if len(system_answers) != len(jsonlines):
                logger.warning(
                    f"Mismatch in number of answers and questions in folder {folder}. Skipping."
                )
                continue
    return


def align_eval_input(eval_system, result_dir="."):
    if os.path.exists(f"{result_dir}/{eval_system}_eval_input.jsonl"):
        open(f"{result_dir}/{eval_system}_eval_input.jsonl", "w").close()
    all_folders = os.listdir("./data/")
    for folder in all_folders:
        if (
            os.path.isdir(f"./data/{folder}")
            and not folder.startswith("__")
            and not folder.startswith(".")
            and not folder.startswith("data")
        ):
            results_path = f"./data/{folder}/{eval_system}_results.txt"
            qa_path = f"./data/{folder}/{folder}_qa.jsonl"
            if not os.path.exists(results_path) or not os.path.exists(qa_path):
                logger.warning(f"Skipping folder {folder} because results or QA file is missing.")
                continue
            system_answers = []
            with open(results_path, "r") as f:
                for line in f.readlines():
                    line = line.strip()
                    if line != "":
                        system_answers.append(line.strip())
            jsonlines = open(qa_path, "r").readlines()
            new_dict_list = []

            lines = []
            for i, jsonline in enumerate(jsonlines):
                js = json.loads(jsonline)
                if js["type"] in ignore_types:
                    continue
                lines.append(jsonline)

            if len(system_answers) != len(lines):
                logger.warning(
                    f"Mismatch in number of answers and questions in folder {folder}. Skipping."
                )
                continue

            for i, jsonline in enumerate(lines):
                system_ans = system_answers[i]
                system_ans = system_ans.lstrip(f"{i+1}.").strip()
                jsonline = json.loads(jsonline)
                jsonline["sys_ans"] = system_ans
                jsonline["file"] = folder
                new_dict_list.append(jsonline)

            with open(f"{result_dir}/{eval_system}_eval_input.jsonl", "a") as f:
                for json_dict in new_dict_list:
                    f.write(json.dumps(json_dict) + "\n")

    return


def evaluate(eval_system, resume_id=0, result_dir="."):
    # read evaluation prompt
    eval_prompt_dir = "./evaluation_prompt.txt"
    eval_prompt = open(eval_prompt_dir).read()
    system_content = "You are a helpful evaluator."

    eval_inp_dir = f"{result_dir}/{eval_system}_eval_input.jsonl"
    eval_out_dir = f"{result_dir}/{eval_system}_eval_output.jsonl"
    if os.path.exists(eval_out_dir):
        open(eval_out_dir, "w").close()

    with open(eval_inp_dir, "r") as f:
        json_dict_list = [json.loads(line) for line in f.readlines()]

    for i, json_dict in enumerate(json_dict_list):
        if i < resume_id:
            continue
        question, sys_ans, ref_ans, ref_text = (
            json_dict["question"],
            json_dict["sys_ans"],
            json_dict["answer"],
            json_dict["evidence"],
        )
        cur_prompt = (
            eval_prompt.replace("{{question}}", question)
            .replace("{{sys_ans}}", sys_ans)
            .replace("{{ref_ans}}", ref_ans)
            .replace("{{ref_text}}", ref_text)
        )
        response = get_gpt_response_openai(cur_prompt, system_content=system_content)
        json_dict["eval"] = response

        with open(eval_out_dir, "a") as f:
            f.write(json.dumps(json_dict) + "\n")
        print(f"-Finish {i}-th qa")
    return


def print_eval_scores(eval_system, result_dir="."):
    import json
    import os

    res_dir = f"{result_dir}/{eval_system}_eval_output.jsonl"
    if not os.path.exists(res_dir):
        print(f"No evaluation output file found at {res_dir}")
        return
    with open(res_dir, "r") as f:
        new_res_list = [json.loads(line) for line in f]
    if not new_res_list:
        print("No results to evaluate.")
        return
    score1 = [res for res in new_res_list if "1" in res["eval"][:20]]
    micro_acc = len(score1) / len(new_res_list)
    types = {
        "text-only": "text",
        "multimodal-f": "mm",
        "multimodal-t": "mm",
        "multimodal": "mm",
        "meta-data": "meta",
        "una": "una",
    }
    file_ranges = {
        "aca": range(0, 49),
        "fin": range(49, 89),
        "gov": range(89, 133),
        "law": range(133, 179),
        "new": range(179, 229),
    }
    type_counts = {key: {"wr": 0, "total": 0} for key in types.values()}
    file_counts = {key: {"cor": 0, "total": 0} for key in file_ranges.keys()}
    passed = []
    failed = []
    for idx, res in enumerate(new_res_list):
        evalres = res["eval"][:20]
        res_type = types.get(res.get("type", "una"), "una")
        if "0" in evalres:
            type_counts[res_type]["wr"] += 1
        type_counts[res_type]["total"] += 1
        try:
            res_file = int(res["file"])
        except Exception:
            res_file = -1
        for key, f_range in file_ranges.items():
            if res_file in f_range:
                if "1" in evalres:
                    file_counts[key]["cor"] += 1
                file_counts[key]["total"] += 1
                break
        # Track pass/fail
        if "1" in evalres:
            passed.append((idx, res.get("file", "?"), res.get("question", "")))
        else:
            failed.append((idx, res.get("file", "?"), res.get("question", "")))
    type_acc = {
        key: 1 - val["wr"] / val["total"] if val["total"] > 0 else 0.0
        for key, val in type_counts.items()
    }
    file_acc = {
        key: val["cor"] / val["total"] if val["total"] > 0 else 0.0
        for key, val in file_counts.items()
    }
    print("\n--- Evaluation Results ---")
    for key, acc in file_acc.items():
        print(f"{key.capitalize()} Accuracy: {acc * 100:.1f}%")
    for key, acc in type_acc.items():
        print(f"{key.capitalize()} Accuracy: {acc * 100:.1f}%")
    print(f"Overall Accuracy: {micro_acc * 100:.1f}%")
    print(f"\nPassed samples ({len(passed)}):")
    for idx, fileid, question in passed:
        print(f"  [PASS] idx={idx}, file={fileid}, Q={question}")
    print(f"\nFailed samples ({len(failed)}):")
    for idx, fileid, question in failed:
        print(f"  [FAIL] idx={idx}, file={fileid}, Q={question}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--system",
        type=str,
        default="",
        choices=[
            "gpt-4o",
            "gpt4",
            "gpt4_pl",
            "gpt-4o_pl",
            "gpt3.5",
            "phi3-medium",
            "commandr-35b",
            "internlm2-20b",
            "internlm2-7b",
            "chatglm3-6b",
            "gpt3.5",
            "llama3-8b",
            "llama3-70b",
            "yi1.5-9b",
            "yi1.5-34b",
            "mixtral-8x7b",
            "mistral-7b",
            "gemma-7b",
            "llama2-13b",
            "kimi",
            "claude3",
            "glm4",
            "qwen2.5",
            "ernie4",
            "gx",
        ],
        help="The name of evaluated system.",
    )
    parser.add_argument(
        "--resume_id", type=int, default=0, help="From which folder to begin evaluation."
    )
    parser.add_argument("--result_dir", type=str, default=".", help="Folder to save results.")

    args = parser.parse_args()

    eval_system = args.system
    resume_id = args.resume_id
    result_dir = args.result_dir

    if eval_system in [
        "gpt-4o",
        "gpt4",
        "gpt4_pl",
        "gpt-4o_pl",
        "gpt3.5",
        "kimi",
        "claude3",
        "glm4",
        "qwen2.5",
        "ernie4",
        "gx",
    ]:
        check_cleansing(eval_system)
        align_eval_input(eval_system, result_dir=result_dir)
    evaluate(eval_system, resume_id=resume_id, result_dir=result_dir)
    print_eval_scores(eval_system, result_dir=result_dir)


if __name__ == "__main__":
    main()
