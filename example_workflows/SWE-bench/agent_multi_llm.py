#!/usr/bin/env python3

"""
Multi-LLM SWE-bench Agent: Orchestrates multiple LLMs to solve SWE-bench issues.

This enhanced agent uses a multi-phase approach:
1. Code Analysis (Claude) - Understands repository structure and problem context
2. Solution Planning (GPT-4) - Creates detailed solution strategy
3. Patch Generation (Multiple LLMs) - Generates candidate patches
4. Validation & Refinement (Claude) - Validates and refines the best patch
5. Error Recovery - Implements retry logic with different strategies

Example:
  python example_workflows/SWE-bench/multi_llm_agent.py \
    --dataset_name princeton-nlp/SWE-bench_Lite \
    --split test \
    --output predictions.jsonl \
    --instance_id sympy__sympy-20590
"""

import argparse
import json
import os
import re
import asyncio
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from datasets import load_dataset

try:
    import anthropic
    from anthropic import AsyncAnthropic
except Exception as e:
    raise RuntimeError(
        "anthropic package is required. Please ensure it is installed and ANTHROPIC_API_KEY is set."
    ) from e

try:
    import openai
    from openai import AsyncOpenAI
except Exception as e:
    raise RuntimeError(
        "openai package is required. Please ensure it is installed and OPENAI_API_KEY is set."
    ) from e


@dataclass
class LLMResponse:
    """Container for LLM responses with metadata."""
    model: str
    phase: str
    content: str
    confidence: float = 0.0
    reasoning: str = ""


class MultiLLMAgent:
    """Orchestrates multiple LLMs to solve SWE-bench issues."""
    
    def __init__(self):
        """Initialize the multi-LLM agent with API clients."""
        # Initialize Claude client
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if not anthropic_key:
            raise SystemExit("Please set ANTHROPIC_API_KEY in your environment.")
        self.claude_client = AsyncAnthropic(api_key=anthropic_key)
        
        # Initialize OpenAI client
        openai_key = os.getenv("OPENAI_API_KEY")
        if not openai_key:
            raise SystemExit("Please set OPENAI_API_KEY in your environment.")
        self.openai_client = AsyncOpenAI(api_key=openai_key)
        
        # Model configurations
        self.models = {
            "claude": "claude-3-7-sonnet-20250219",
            "gpt4": "gpt-4-turbo-preview",
            "gpt3": "gpt-3.5-turbo"
        }
    
    def _strip_code_fences(self, text: str) -> str:
        """Remove surrounding triple backtick fences if present."""
        text = text.strip()
        fence_match = re.match(r"^```[a-zA-Z0-9_-]*\n([\s\S]*?)\n```$", text)
        if fence_match:
            return fence_match.group(1).strip()
        text = re.sub(r"^```[a-zA-Z0-9_-]*\n", "", text)
        text = re.sub(r"\n```$", "", text)
        return text.strip()
    
    async def phase1_code_analysis(self, instance: dict) -> LLMResponse:
        """
        Phase 1: Use Claude to analyze the code and understand the problem.
        
        This phase focuses on:
        - Understanding the repository structure
        - Identifying relevant files and functions
        - Analyzing the problem statement
        - Creating a context summary
        """
        problem = instance.get("problem_statement", "")
        repo = instance.get("repo", "")
        base_commit = instance.get("base_commit", "")
        
        prompt = f"""You are an expert software engineer analyzing a bug report for the SWE-bench benchmark.

Repository: {repo}
Base commit: {base_commit}

Problem Statement:
{problem}

Please analyze this issue and provide:
1. A summary of the problem
2. Likely files that need to be modified
3. Key functions or classes involved
4. Root cause analysis
5. Potential solution approaches

Format your response as JSON with the following structure:
{{
    "problem_summary": "...",
    "affected_files": ["file1.py", "file2.py"],
    "key_components": ["function_name", "ClassName"],
    "root_cause": "...",
    "solution_approaches": ["approach1", "approach2"],
    "confidence": 0.85
}}"""
        
        msg = await self.claude_client.messages.create(
            model=self.models["claude"],
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        content = ""
        for part in msg.content:
            text = getattr(part, "text", None)
            if text:
                content += text
        
        return LLMResponse(
            model="claude",
            phase="code_analysis",
            content=content,
            confidence=0.85,
            reasoning="Initial code analysis and problem understanding"
        )
    
    async def phase2_solution_planning(self, instance: dict, analysis: LLMResponse) -> LLMResponse:
        """
        Phase 2: Use GPT-4 to create a detailed solution plan.
        
        This phase focuses on:
        - Creating step-by-step implementation plan
        - Identifying edge cases
        - Planning test scenarios
        """
        problem = instance.get("problem_statement", "")
        repo = instance.get("repo", "")
        
        prompt = f"""You are an expert software engineer planning a solution for a bug fix.

Repository: {repo}
Problem: {problem}

Previous Analysis:
{analysis.content}

Create a detailed implementation plan that includes:
1. Step-by-step changes needed
2. Code modifications with pseudo-code
3. Edge cases to handle
4. Test scenarios to verify the fix
5. Potential risks or side effects

Format your response as a structured plan with clear sections."""
        
        response = await self.openai_client.chat.completions.create(
            model=self.models["gpt4"],
            messages=[
                {"role": "system", "content": "You are an expert software engineer skilled in planning bug fixes."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=2000,
            temperature=0.3
        )
        
        content = response.choices[0].message.content
        
        return LLMResponse(
            model="gpt4",
            phase="solution_planning",
            content=content,
            confidence=0.80,
            reasoning="Detailed solution planning with GPT-4"
        )
    
    async def phase3_patch_generation(self, instance: dict, analysis: LLMResponse, plan: LLMResponse) -> List[LLMResponse]:
        """
        Phase 3: Generate multiple candidate patches using different LLMs.
        
        This phase:
        - Generates patches from multiple LLMs
        - Uses different prompting strategies
        - Creates diverse solution candidates
        """
        problem = instance.get("problem_statement", "")
        repo = instance.get("repo", "")
        base_commit = instance.get("base_commit", "")
        
        patches = []
        
        # Generate patch with Claude (detailed, conservative approach)
        claude_prompt = f"""Generate a unified diff patch for this issue.

Repository: {repo}
Base commit: {base_commit}
Problem: {problem}

Analysis:
{analysis.content}

Plan:
{plan.content}

Requirements:
- Output ONLY a valid unified diff patch
- Use paths prefixed with a/ and b/
- Include correct @@ hunk headers
- Be conservative and make minimal changes
- Ensure the patch applies cleanly

Output the patch directly without any explanation or markdown fences."""
        
        claude_msg = await self.claude_client.messages.create(
            model=self.models["claude"],
            max_tokens=3000,
            messages=[{"role": "user", "content": claude_prompt}]
        )
        
        claude_content = ""
        for part in claude_msg.content:
            text = getattr(part, "text", None)
            if text:
                claude_content += text
        
        patches.append(LLMResponse(
            model="claude",
            phase="patch_generation",
            content=self._strip_code_fences(claude_content),
            confidence=0.85,
            reasoning="Conservative patch with minimal changes"
        ))
        
        # Generate patch with GPT-4 (comprehensive approach)
        gpt4_prompt = f"""Generate a unified diff patch to fix this issue.

Repository: {repo}
Problem: {problem}

Based on this plan:
{plan.content}

Create a comprehensive patch that:
1. Fixes the main issue
2. Handles edge cases
3. Maintains backward compatibility

Output only the unified diff patch in proper format."""
        
        gpt4_response = await self.openai_client.chat.completions.create(
            model=self.models["gpt4"],
            messages=[
                {"role": "system", "content": "Generate only a unified diff patch, no explanations."},
                {"role": "user", "content": gpt4_prompt}
            ],
            max_tokens=3000,
            temperature=0.2
        )
        
        patches.append(LLMResponse(
            model="gpt4",
            phase="patch_generation",
            content=self._strip_code_fences(gpt4_response.choices[0].message.content),
            confidence=0.80,
            reasoning="Comprehensive patch with edge case handling"
        ))
        
        # Generate patch with GPT-3.5 (quick, straightforward approach)
        gpt3_prompt = f"""Fix this bug by generating a unified diff patch.

Problem: {problem}

Key changes needed:
{self._extract_key_changes(plan.content)}

Output format: unified diff patch only."""
        
        gpt3_response = await self.openai_client.chat.completions.create(
            model=self.models["gpt3"],
            messages=[
                {"role": "user", "content": gpt3_prompt}
            ],
            max_tokens=2000,
            temperature=0.1
        )
        
        patches.append(LLMResponse(
            model="gpt3",
            phase="patch_generation",
            content=self._strip_code_fences(gpt3_response.choices[0].message.content),
            confidence=0.70,
            reasoning="Quick straightforward patch"
        ))
        
        return patches
    
    async def phase4_validation_refinement(self, patches: List[LLMResponse], instance: dict) -> LLMResponse:
        """
        Phase 4: Validate and refine patches using Claude.
        
        This phase:
        - Evaluates all candidate patches
        - Selects the best approach
        - Refines and improves the selected patch
        """
        problem = instance.get("problem_statement", "")
        repo = instance.get("repo", "")
        
        # Prepare patches for evaluation
        patches_text = "\n\n".join([
            f"=== Patch {i+1} (Model: {p.model}, Confidence: {p.confidence}) ===\n{p.content}"
            for i, p in enumerate(patches)
        ])
        
        prompt = f"""You are reviewing multiple patches for a bug fix in {repo}.

Problem: {problem}

Candidate Patches:
{patches_text}

Please:
1. Evaluate each patch for correctness and completeness
2. Identify the best approach or combine the best parts
3. Generate a refined, production-ready patch

Criteria for evaluation:
- Correctness: Does it fix the issue?
- Completeness: Are edge cases handled?
- Minimalism: Are changes minimal and focused?
- Safety: No unintended side effects?

Output only the final refined unified diff patch."""
        
        msg = await self.claude_client.messages.create(
            model=self.models["claude"],
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        content = ""
        for part in msg.content:
            text = getattr(part, "text", None)
            if text:
                content += text
        
        return LLMResponse(
            model="claude",
            phase="validation_refinement",
            content=self._strip_code_fences(content),
            confidence=0.90,
            reasoning="Validated and refined patch combining best approaches"
        )
    
    async def phase5_error_recovery(self, instance: dict, error: str) -> LLMResponse:
        """
        Phase 5: Error recovery with alternative strategies.
        
        This phase handles failures by:
        - Analyzing what went wrong
        - Trying alternative approaches
        - Simplifying the solution if needed
        """
        problem = instance.get("problem_statement", "")
        repo = instance.get("repo", "")
        
        prompt = f"""Previous patch generation failed with error:
{error}

Repository: {repo}
Problem: {problem}

Generate a simpler, more conservative patch that:
1. Makes minimal changes
2. Focuses only on the core issue
3. Avoids complex refactoring

Output only a valid unified diff patch."""
        
        msg = await self.claude_client.messages.create(
            model=self.models["claude"],
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        content = ""
        for part in msg.content:
            text = getattr(part, "text", None)
            if text:
                content += text
        
        return LLMResponse(
            model="claude",
            phase="error_recovery",
            content=self._strip_code_fences(content),
            confidence=0.75,
            reasoning="Simplified patch after error recovery"
        )
    
    def _extract_key_changes(self, plan_content: str) -> str:
        """Extract key changes from the planning phase."""
        # Simple extraction of key points
        lines = plan_content.split('\n')
        key_lines = [l for l in lines if any(
            keyword in l.lower() for keyword in 
            ['change', 'modify', 'add', 'remove', 'fix', 'update']
        )]
        return '\n'.join(key_lines[:5])  # Return top 5 key changes
    
    async def solve_instance(self, instance: dict) -> str:
        """
        Main orchestration method that runs all phases.
        
        Returns the final patch as a string.
        """
        try:
            # Phase 1: Code Analysis
            print("Phase 1: Analyzing code and problem...")
            analysis = await self.phase1_code_analysis(instance)
            
            # Phase 2: Solution Planning
            print("Phase 2: Planning solution strategy...")
            plan = await self.phase2_solution_planning(instance, analysis)
            
            # Phase 3: Patch Generation (parallel)
            print("Phase 3: Generating candidate patches...")
            patches = await self.phase3_patch_generation(instance, analysis, plan)
            
            # Phase 4: Validation and Refinement
            print("Phase 4: Validating and refining patches...")
            final_patch = await self.phase4_validation_refinement(patches, instance)
            
            return final_patch.content
            
        except Exception as e:
            print(f"Error occurred: {e}")
            print("Phase 5: Attempting error recovery...")
            recovery_patch = await self.phase5_error_recovery(instance, str(e))
            return recovery_patch.content


def main():
    parser = argparse.ArgumentParser(description="Multi-LLM SWE-bench Agent")
    parser.add_argument(
        "--dataset_name",
        type=str,
        default="princeton-nlp/SWE-bench_Lite",
        help="Hugging Face dataset name",
    )
    parser.add_argument(
        "--split",
        type=str,
        default="test",
        help="Dataset split (e.g., dev or test)",
    )
    parser.add_argument(
        "--instance_id",
        type=str,
        default=None,
        help="Specific instance_id to predict",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="multi_llm_predictions.jsonl",
        help="Path to write predictions JSONL",
    )
    parser.add_argument(
        "--max_instances",
        type=int,
        default=1,
        help="Maximum number of instances to process",
    )
    args = parser.parse_args()
    
    # Load dataset
    ds = load_dataset(args.dataset_name, split=args.split)
    
    # Select instances to process
    if args.instance_id:
        matches = [row for row in ds if row.get("instance_id") == args.instance_id]
        if not matches:
            raise SystemExit(f"instance_id not found in dataset: {args.instance_id}")
        instances = matches[:1]
    else:
        instances = list(ds)[:args.max_instances]
    
    # Initialize agent
    agent = MultiLLMAgent()
    
    # Process instances
    predictions = []
    for i, instance in enumerate(instances):
        print(f"\nProcessing instance {i+1}/{len(instances)}: {instance['instance_id']}")
        
        # Run async solver
        patch = asyncio.run(agent.solve_instance(instance))
        
        # Prepare prediction entry
        pred = {
            "instance_id": instance["instance_id"],
            "model_name_or_path": "multi-llm-agent",
            "model_patch": patch,
        }
        predictions.append(pred)
        
        print(f"✓ Generated patch for {instance['instance_id']}")
    
    # Write predictions
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for pred in predictions:
            f.write(json.dumps(pred) + "\n")
    
    print(f"\n✓ Wrote {len(predictions)} predictions to: {out_path.resolve()}")
    print(
        "\nRun evaluation:\n"
        "  python -m swebench.harness.run_evaluation \\\n"
        f"    --dataset_name {args.dataset_name} \\\n"
        f"    --predictions_path {out_path.resolve()} \\\n"
        "    --max_workers 4 \\\n"
        "    --run_id multi_llm_agent\n"
    )


if __name__ == "__main__":
    main()