instructions = """I'm translating code from a high-level decsription into runnable python code using LLMs. I take several steps to do this, and my final code is wrong. I want to figure out which was the first step that was to unclear or incorrect, such that the later steps couldn't recover from that failure. Erros could include describing a wrong design, being to inconcise, or simply not producing the right code although the previously described approach is perfectly clear. Be critical in your analysis of every step and consider each step as a possible root cause for the final error (i.e., even steps that don't produce code may be inconcise and therefore result in the wrong code). The code is part of a larger code base. The high-level task description describes functionality and what dependencies to use (e.g., dependencies inside the repo and extermal packages).

1. First, I'm doing an aanlysis of the high-level text. This produces a difficulty rating and XXX.
2. Second, I'm planning the implementation in several iterations. This produces high-level code that becomes more and more concrete.
3. I'm generating the actual source code. I will give you the code here and a review that the LLM gets on the generated code.

Below are all the step's:

---------------------------------------------
Step 1: Analyzing the high-level task description:

{analysis}"""

"""
---------------------------------------------
Step {iter}: Iteratively planning the implementation:

{plan}
---------------------------------------------
Step {iter}: Implementing the actual code (implementation and review):

Implemmentation:
{implementation}

Review:
{review}
---------------------------------------------
"""



plan_prompt = """
---------------------------------------------
Step {iter}: Iteratively planning the implementation:

Produced plan (iteratively refined Python code):

{plan}

Performed steps:

{analysis}
"""



impl_prompt = """
---------------------------------------------
Step {iter}: Implementing the actual code (implementation and review):

Implemmentation:

{implementation}

Review:

{review}
"""

suffix = """
In your response, describe what step is the root cause of the wrong code generation (i.e., after which step what the LLM chain not able to recover --- e.g, because it's too vaguely or badly planned, or the LLM generated incorrect code although the task was perfectly clear). First, reason about what went wrong in the generation process. Then, describe where it went wrong first. Then describe what is necessary to avoid this failure.
"""
