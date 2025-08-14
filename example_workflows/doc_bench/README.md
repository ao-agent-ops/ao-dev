
# DocBench

 - Paper: https://arxiv.org/pdf/2407.10701

 - Task: Answer questions about PDFs

 - See original_README.md for the authors' README.

## Run

### 1. Install

Data can be downloaded from: https://drive.google.com/drive/folders/1yxhF1lFF2gKeTNc8Wh0EyBdMT3M4pDYr?usp=sharing 

Place in doc_bench/data

Our dev conda env has all dependencies installed.


### 2. Produce outputs

Each subdir (e.g., `doc_bench/data/0`) has (1) a PDF and (2) a jsonl with questions.

`python run.py --system gpt-4o` runs predictions on all folders.


**Available  "systems" (and adding your own):**

The benchmark provides a bunch of single-LLM-call solutions:

 - gpt-4o, gpt4, gpt4_pl, gpt-4o_pl, gpt3.5, phi3-medium, commandr-35b, internlm2-20b, internlm2-7b, chatglm3-6b, gpt3.5, llama3-8b, llama3-70b, yi1.5-9b, yi1.5-34b, mixtral-8x7b, mistral-7b, gemma-7b, llama2-13b, kimi, claude3, glm4, qwen2.5, ernie4, gx

We provide `your_agent_workflow.py` as example, and you can implement your workflow there. To add another one:

1. Create file where you implement your stuff. Have some callable function to run it.
   -  E.g., `def your_agent_workflow(pdf_path, q_string, folder)`
  
2. Import your function in `run.py`
   - E.g., `from your_agent_workflow import your_agent_workflow`
  
3. `your_agents_register.py` has a list with identifiers for your agent workflows. Add how you want the eval to call your workflow.
   - E.g., `your_agents = [..., "your_agent_workflow"]` 
  
4. In `run.py`, `Runner.run()` make an if statement where, if `self.systems` is your identifier, it should execute your imported function.
   - E.g.:
 ```
elif self.system == "your_agent_workflow":
    pdf_path = file_content
    response = your_agent_workflow(pdf_path, q_string, folder)
 ``` 

5. Done. You should be able to run commands like `python run.py --system your_agent_workflow` or `python evaluate.py --system your_agent_workflow`


**Running a subset of samples:**

 - `--initial_folder 90` controls first folder to process (inclusive, so 90 is processed as well). 

 - `--total_folder_number 100` controls last folder to process (inlusive, so folder 100 is processed as well)


**Output:**

 - In each folder, places a file like `gpt-4o_results.txt`.


### 3. Evaluate outputs

`python evaluate.py --system gpt-4o` means you want to evaluate all gpt-4o answers you produced in the previous step.

It will output `results/gpt-4o_eval_output.jsonl` and will print metrics.


**Evaluate subset**

Probably you don't need this. Index is over *questions* not *samples*. Every sample has several questions.

 - `--resume_id`: Question to start from.
 - `--max_samples`: Number of samples to use in evaluation (starting from `resume_id`). If there's too few, it won't go back to beginning.


**Evaluation method**

`gpt-4-0125-preview` compares the answer to ground truth and says correct/wrong. 

