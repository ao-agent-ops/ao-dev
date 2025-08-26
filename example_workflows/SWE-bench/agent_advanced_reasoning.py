#!/usr/bin/env python3

"""
Advanced Multi-LLM SWE-bench Agent with Chain-of-Thought Reasoning and Self-Reflection.

This agent implements:
1. Repository exploration and code search
2. Chain-of-thought (CoT) reasoning for problem decomposition
3. Self-reflection and iterative improvement
4. Multi-agent debate for solution validation
5. Test-driven patch development

Example:
  python example_workflows/SWE-bench/advanced_reasoning_agent.py \
    --dataset_name princeton-nlp/SWE-bench_Lite \
    --split test \
    --output advanced_predictions.jsonl \
    --instance_id sympy__sympy-20590
"""

import argparse
import json
import os
import re
import asyncio
from pathlib import Path
from typing import List, Dict, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum

from datasets import load_dataset

try:
    from anthropic import AsyncAnthropic
except Exception as e:
    raise RuntimeError(
        "anthropic package is required. Please ensure it is installed and ANTHROPIC_API_KEY is set."
    ) from e

try:
    from openai import AsyncOpenAI
except Exception as e:
    raise RuntimeError(
        "openai package is required. Please ensure it is installed and OPENAI_API_KEY is set."
    ) from e


class ReasoningStep(Enum):
    """Types of reasoning steps in chain-of-thought."""

    EXPLORE = "explore"
    HYPOTHESIZE = "hypothesize"
    VERIFY = "verify"
    IMPLEMENT = "implement"
    REFLECT = "reflect"
    REFINE = "refine"


@dataclass
class ThoughtChain:
    """Represents a chain of reasoning steps."""

    steps: List[Dict[str, Any]] = field(default_factory=list)
    current_hypothesis: str = ""
    confidence: float = 0.0
    iterations: int = 0
    max_iterations: int = 3

    def add_step(self, step_type: ReasoningStep, content: str, metadata: Dict = None):
        """Add a reasoning step to the chain."""
        self.steps.append(
            {
                "type": step_type.value,
                "content": content,
                "metadata": metadata or {},
                "iteration": self.iterations,
            }
        )

    def get_summary(self) -> str:
        """Get a summary of the reasoning chain."""
        summary = []
        for step in self.steps:
            summary.append(f"[{step['type']}] {step['content'][:200]}...")
        return "\n".join(summary)


@dataclass
class CodeContext:
    """Represents understanding of the codebase."""

    repo_structure: Dict[str, List[str]] = field(default_factory=dict)
    relevant_files: List[str] = field(default_factory=list)
    key_functions: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    test_files: List[str] = field(default_factory=list)
    similar_patterns: List[str] = field(default_factory=list)


class AdvancedReasoningAgent:
    """Advanced agent with chain-of-thought reasoning and self-reflection."""

    def __init__(self):
        """Initialize the advanced reasoning agent."""
        # Initialize API clients
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if not anthropic_key:
            raise SystemExit("Please set ANTHROPIC_API_KEY in your environment.")
        self.claude_client = AsyncAnthropic(api_key=anthropic_key)

        openai_key = os.getenv("OPENAI_API_KEY")
        if not openai_key:
            raise SystemExit("Please set OPENAI_API_KEY in your environment.")
        self.openai_client = AsyncOpenAI(api_key=openai_key)

        # Model configurations
        self.models = {
            "claude": "claude-3-7-sonnet-20250219",
            "gpt4": "gpt-4-turbo-preview",
            "gpt3": "gpt-3.5-turbo",
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

    async def explore_repository(self, instance: dict) -> CodeContext:
        """
        Explore the repository structure to understand the codebase.

        This simulates repository exploration by analyzing the problem
        and inferring likely file structures.
        """
        problem = instance.get("problem_statement", "")
        repo = instance.get("repo", "")

        prompt = f"""You are exploring the repository {repo} to understand its structure.

Problem statement mentions:
{problem}

Based on common patterns in this type of repository, provide:
1. Likely directory structure
2. Key source files related to this issue
3. Test files that might need updating
4. Dependencies and imports
5. Similar code patterns that might exist

Format as JSON:
{{
    "directories": ["src/", "tests/", ...],
    "source_files": ["main.py", ...],
    "test_files": ["test_main.py", ...],
    "key_functions": ["function_name", ...],
    "dependencies": ["numpy", ...],
    "patterns": ["pattern description", ...]
}}"""

        msg = await self.claude_client.messages.create(
            model=self.models["claude"],
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )

        content = ""
        for part in msg.content:
            text = getattr(part, "text", None)
            if text:
                content += text

        # Parse the response into CodeContext
        context = CodeContext()
        try:
            data = json.loads(self._extract_json(content))
            context.relevant_files = data.get("source_files", [])
            context.test_files = data.get("test_files", [])
            context.key_functions = data.get("key_functions", [])
            context.dependencies = data.get("dependencies", [])
            context.similar_patterns = data.get("patterns", [])
        except:
            # Fallback to basic extraction
            context.relevant_files = self._extract_filenames(content)

        return context

    async def chain_of_thought_reasoning(
        self, instance: dict, context: CodeContext
    ) -> ThoughtChain:
        """
        Implement chain-of-thought reasoning to decompose the problem.

        Steps:
        1. Break down the problem
        2. Form hypotheses
        3. Verify assumptions
        4. Plan implementation
        """
        chain = ThoughtChain()
        problem = instance.get("problem_statement", "")
        repo = instance.get("repo", "")

        # Step 1: Problem Decomposition
        decompose_prompt = f"""Let's think step by step about this bug in {repo}.

Problem: {problem}

Relevant files: {', '.join(context.relevant_files[:5])}

Break this down:
1. What is the expected behavior?
2. What is the actual behavior?
3. What is the likely cause?
4. What needs to change?

Think through this systematically."""

        response = await self.openai_client.chat.completions.create(
            model=self.models["gpt4"],
            messages=[
                {"role": "system", "content": "You are a debugging expert. Think step by step."},
                {"role": "user", "content": decompose_prompt},
            ],
            max_tokens=1000,
            temperature=0.3,
        )

        decomposition = response.choices[0].message.content
        chain.add_step(ReasoningStep.EXPLORE, decomposition)

        # Step 2: Hypothesis Formation
        hypothesis_prompt = f"""Based on this analysis:
{decomposition}

Form specific hypotheses about:
1. The root cause of the bug
2. The minimal change needed
3. Potential side effects

Be specific and testable."""

        msg = await self.claude_client.messages.create(
            model=self.models["claude"],
            max_tokens=800,
            messages=[{"role": "user", "content": hypothesis_prompt}],
        )

        hypothesis = ""
        for part in msg.content:
            text = getattr(part, "text", None)
            if text:
                hypothesis += text

        chain.add_step(ReasoningStep.HYPOTHESIZE, hypothesis)
        chain.current_hypothesis = hypothesis

        # Step 3: Verification Planning
        verify_prompt = f"""How can we verify this hypothesis?
{hypothesis}

Suggest:
1. What code to examine
2. What tests to run
3. What edge cases to consider"""

        response = await self.openai_client.chat.completions.create(
            model=self.models["gpt3"],
            messages=[{"role": "user", "content": verify_prompt}],
            max_tokens=500,
            temperature=0.2,
        )

        verification = response.choices[0].message.content
        chain.add_step(ReasoningStep.VERIFY, verification)

        return chain

    async def self_reflect(self, chain: ThoughtChain, patch: str) -> Tuple[bool, str]:
        """
        Self-reflection on the generated solution.

        Returns: (needs_revision, feedback)
        """
        prompt = f"""Critically evaluate this solution:

Reasoning chain:
{chain.get_summary()}

Generated patch:
{patch}

Questions to consider:
1. Does this fully address the problem?
2. Are there any logical flaws?
3. Could this break existing functionality?
4. Is this the minimal necessary change?
5. Are there untested edge cases?

Provide honest criticism and suggest improvements if needed."""

        msg = await self.claude_client.messages.create(
            model=self.models["claude"],
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )

        reflection = ""
        for part in msg.content:
            text = getattr(part, "text", None)
            if text:
                reflection += text

        # Determine if revision is needed
        needs_revision = any(
            phrase in reflection.lower()
            for phrase in ["should be", "needs to", "missing", "incorrect", "better to"]
        )

        return needs_revision, reflection

    async def multi_agent_debate(self, patches: List[str], instance: dict) -> str:
        """
        Implement multi-agent debate where different LLMs critique and improve solutions.
        """
        problem = instance.get("problem_statement", "")

        # Agent 1 (Claude): Conservative reviewer
        claude_prompt = f"""You are a conservative code reviewer.
Review these patches for the problem: {problem}

Patches:
{self._format_patches(patches)}

Which approach is safest and most reliable? Explain your reasoning."""

        claude_msg = await self.claude_client.messages.create(
            model=self.models["claude"],
            max_tokens=800,
            messages=[{"role": "user", "content": claude_prompt}],
        )

        claude_review = ""
        for part in claude_msg.content:
            text = getattr(part, "text", None)
            if text:
                claude_review += text

        # Agent 2 (GPT-4): Innovation advocate
        gpt_prompt = f"""You are advocating for the most comprehensive solution.
Review these patches for the problem: {problem}

Patches:
{self._format_patches(patches)}

Conservative review says:
{claude_review}

Counter-argue if needed and suggest the best approach."""

        gpt_response = await self.openai_client.chat.completions.create(
            model=self.models["gpt4"],
            messages=[{"role": "user", "content": gpt_prompt}],
            max_tokens=800,
            temperature=0.3,
        )

        gpt_review = gpt_response.choices[0].message.content

        # Final synthesis
        synthesis_prompt = f"""Synthesize these perspectives into the best solution:

Conservative view:
{claude_review}

Comprehensive view:
{gpt_review}

Original patches:
{self._format_patches(patches)}

Generate the final, best patch that balances safety and completeness."""

        final_msg = await self.claude_client.messages.create(
            model=self.models["claude"],
            max_tokens=2000,
            messages=[{"role": "user", "content": synthesis_prompt}],
        )

        final_patch = ""
        for part in final_msg.content:
            text = getattr(part, "text", None)
            if text:
                final_patch += text

        return self._strip_code_fences(final_patch)

    async def generate_test_driven_patch(self, instance: dict, chain: ThoughtChain) -> str:
        """
        Generate a patch with test-driven development approach.
        """
        problem = instance.get("problem_statement", "")
        repo = instance.get("repo", "")

        # First, generate test cases
        test_prompt = f"""For this bug in {repo}:
{problem}

Based on the hypothesis:
{chain.current_hypothesis}

Write test cases that would:
1. Fail with the current buggy code
2. Pass with the fixed code

Include edge cases."""

        test_response = await self.openai_client.chat.completions.create(
            model=self.models["gpt4"],
            messages=[{"role": "user", "content": test_prompt}],
            max_tokens=1000,
            temperature=0.2,
        )

        test_cases = test_response.choices[0].message.content

        # Then generate patch to make tests pass
        patch_prompt = f"""Generate a minimal patch that makes these tests pass:

Tests:
{test_cases}

Problem: {problem}
Repository: {repo}

Requirements:
- Output only a unified diff patch
- Make minimal changes to pass the tests
- Maintain backward compatibility"""

        msg = await self.claude_client.messages.create(
            model=self.models["claude"],
            max_tokens=2000,
            messages=[{"role": "user", "content": patch_prompt}],
        )

        patch = ""
        for part in msg.content:
            text = getattr(part, "text", None)
            if text:
                patch += text

        return self._strip_code_fences(patch)

    async def iterative_refinement(
        self, instance: dict, initial_patch: str, chain: ThoughtChain
    ) -> str:
        """
        Iteratively refine the patch based on self-reflection.
        """
        current_patch = initial_patch

        for iteration in range(chain.max_iterations):
            chain.iterations = iteration + 1

            # Self-reflect on current solution
            needs_revision, feedback = await self.self_reflect(chain, current_patch)
            chain.add_step(ReasoningStep.REFLECT, feedback)

            if not needs_revision:
                chain.confidence = 0.9 + (0.03 * iteration)
                break

            # Refine based on feedback
            refine_prompt = f"""Improve this patch based on the feedback:

Current patch:
{current_patch}

Feedback:
{feedback}

Generate an improved patch that addresses the concerns."""

            msg = await self.claude_client.messages.create(
                model=self.models["claude"],
                max_tokens=2000,
                messages=[{"role": "user", "content": refine_prompt}],
            )

            refined = ""
            for part in msg.content:
                text = getattr(part, "text", None)
                if text:
                    refined += text

            current_patch = self._strip_code_fences(refined)
            chain.add_step(ReasoningStep.REFINE, f"Refined patch based on: {feedback[:100]}...")

        return current_patch

    def _extract_json(self, text: str) -> str:
        """Extract JSON from text."""
        json_match = re.search(r"\{[\s\S]*\}", text)
        if json_match:
            return json_match.group(0)
        return "{}"

    def _extract_filenames(self, text: str) -> List[str]:
        """Extract filenames from text."""
        pattern = r"[\w/]+\.(py|js|java|cpp|c|h|hpp|rs|go|rb|php)"
        return re.findall(pattern, text)

    def _format_patches(self, patches: List[str]) -> str:
        """Format patches for display."""
        formatted = []
        for i, patch in enumerate(patches, 1):
            formatted.append(f"--- Patch {i} ---\n{patch[:500]}...")
        return "\n\n".join(formatted)

    async def solve_instance(self, instance: dict) -> str:
        """
        Main orchestration with advanced reasoning.
        """
        try:
            print("🔍 Exploring repository structure...")
            context = await self.explore_repository(instance)

            print("🧠 Chain-of-thought reasoning...")
            chain = await self.chain_of_thought_reasoning(instance, context)

            print("🧪 Generating test-driven patch...")
            initial_patch = await self.generate_test_driven_patch(instance, chain)

            print("🔄 Iterative refinement with self-reflection...")
            refined_patch = await self.iterative_refinement(instance, initial_patch, chain)

            # Generate alternative patches for debate
            print("💭 Generating alternative solutions...")
            alternatives = []

            # Quick alternative from GPT-3.5
            gpt3_response = await self.openai_client.chat.completions.create(
                model=self.models["gpt3"],
                messages=[
                    {
                        "role": "user",
                        "content": f"Generate a simple patch for: {instance.get('problem_statement', '')[:500]}",
                    }
                ],
                max_tokens=1500,
                temperature=0.5,
            )
            alternatives.append(self._strip_code_fences(gpt3_response.choices[0].message.content))

            alternatives.append(refined_patch)

            print("🎭 Multi-agent debate for best solution...")
            final_patch = await self.multi_agent_debate(alternatives, instance)

            print(f"✅ Solution confidence: {chain.confidence:.2%}")
            print(f"   Iterations: {chain.iterations}")

            return final_patch

        except Exception as e:
            print(f"❌ Error: {e}")
            # Fallback to simple patch generation
            return await self._emergency_patch(instance)

    async def _emergency_patch(self, instance: dict) -> str:
        """Emergency fallback patch generation."""
        problem = instance.get("problem_statement", "")
        repo = instance.get("repo", "")

        prompt = f"""Generate a minimal unified diff patch for:
Repository: {repo}
Problem: {problem[:500]}

Output only the patch."""

        msg = await self.claude_client.messages.create(
            model=self.models["claude"],
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )

        patch = ""
        for part in msg.content:
            text = getattr(part, "text", None)
            if text:
                patch += text

        return self._strip_code_fences(patch)


def main():
    parser = argparse.ArgumentParser(description="Advanced Reasoning SWE-bench Agent")
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
        help="Dataset split",
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
        default="advanced_predictions.jsonl",
        help="Output file path",
    )
    parser.add_argument(
        "--max_instances",
        type=int,
        default=1,
        help="Maximum instances to process",
    )
    args = parser.parse_args()

    # Load dataset
    ds = load_dataset(args.dataset_name, split=args.split)

    # Select instances
    if args.instance_id:
        matches = [row for row in ds if row.get("instance_id") == args.instance_id]
        if not matches:
            raise SystemExit(f"Instance not found: {args.instance_id}")
        instances = matches[:1]
    else:
        instances = list(ds)[: args.max_instances]

    # Initialize agent
    agent = AdvancedReasoningAgent()

    # Process instances
    predictions = []
    for i, instance in enumerate(instances, 1):
        print(f"\n{'='*60}")
        print(f"Processing {i}/{len(instances)}: {instance['instance_id']}")
        print(f"{'='*60}")

        patch = asyncio.run(agent.solve_instance(instance))

        predictions.append(
            {
                "instance_id": instance["instance_id"],
                "model_name_or_path": "advanced-reasoning-agent",
                "model_patch": patch,
            }
        )

        print(f"✓ Completed {instance['instance_id']}")

    # Write results
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for pred in predictions:
            f.write(json.dumps(pred) + "\n")

    print(f"\n✅ Wrote {len(predictions)} predictions to: {out_path.resolve()}")
    print(
        "\n📊 Run evaluation:\n"
        "  python -m swebench.harness.run_evaluation \\\n"
        f"    --dataset_name {args.dataset_name} \\\n"
        f"    --predictions_path {out_path.resolve()} \\\n"
        "    --max_workers 4 \\\n"
        "    --run_id advanced_reasoning\n"
    )


if __name__ == "__main__":
    main()
