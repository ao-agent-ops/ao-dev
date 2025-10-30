#!/usr/bin/env python3
"""
LangChain Multi-Agent Team Example

This program demonstrates a team of specialized agents working together to solve a complex problem.
It showcases various LangChain methods that are patched for tracking:
- BaseChatModel.invoke
- BaseLanguageModel.generate  
- BaseLanguageModel.generate_prompt
- BaseChatModel.generate
- Async versions of the above

The scenario: A research team consisting of:
1. Research Agent - Gathers information
2. Analysis Agent - Analyzes the research
3. Writing Agent - Writes the final report
4. Review Agent - Reviews and improves the report
"""

import os
import asyncio
from langchain_openai import ChatOpenAI, OpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import PromptTemplate

# Ensure API key is set for testing
if not os.environ.get("OPENAI_API_KEY"):
    print("[user_program] OPENAI_API_KEY not set, setting dummy key")
    os.environ["OPENAI_API_KEY"] = "sk-test-dummy-key"

print(f"[user_program] Creating LangChain agents with API key: {os.environ.get('OPENAI_API_KEY', 'NOT_SET')[:20]}...")

# Create different models for different agents
research_agent = ChatOpenAI(model="gpt-3.5-turbo", temperature=0.7)
analysis_agent = ChatOpenAI(model="gpt-4", temperature=0.3)
writing_agent = ChatOpenAI(model="gpt-3.5-turbo", temperature=0.5)
review_agent = ChatOpenAI(model="gpt-4", temperature=0.1)
# Non-chat model for demonstrating BaseLanguageModel.generate
summary_agent = OpenAI(model="gpt-3.5-turbo-instruct", temperature=0.2)

print("[user_program] LangChain agents created successfully")

# The research topic
research_topic = "the impact of artificial intelligence on software development"

print(f"[user_program] Starting research on: {research_topic}")

# =============================================================================
# STEP 1: Research Agent - Uses BaseChatModel.invoke
# =============================================================================
print("\n[STEP 1] Research Agent gathering information...")

research_messages = [
    SystemMessage(content="You are a research agent. Gather key information on the given topic and provide 3 main points."),
    HumanMessage(content=f"Research {research_topic} and provide 3 key insights.")
]

research_result = research_agent.invoke(research_messages)
print(f"[Research Agent] {research_result.content[:100]}...")

# =============================================================================
# STEP 2: Analysis Agent - Uses BaseChatModel.generate with multiple conversations
# =============================================================================
print("\n[STEP 2] Analysis Agent analyzing research...")

# Create multiple conversation threads for batch analysis
analysis_conversations = [
    [HumanMessage(content=f"Analyze this research and identify the most important trend: {research_result.content}")],
    [HumanMessage(content=f"What are the implications of this research: {research_result.content}")],
    [HumanMessage(content=f"What questions remain unanswered: {research_result.content}")]
]

# Use generate method for batch processing of conversations
analysis_result = analysis_agent.generate(analysis_conversations)
print(f"[Analysis Agent] Generated {len(analysis_result.generations)} analyses")
for i, gen_list in enumerate(analysis_result.generations):
    if gen_list and hasattr(gen_list[0], 'message'):
        print(f"  Analysis {i+1}: {gen_list[0].message.content[:50]}...")

# =============================================================================
# STEP 3: Writing Agent - Uses BaseLanguageModel.generate_prompt
# =============================================================================
print("\n[STEP 3] Writing Agent creating report...")

# Create PromptTemplate for generate_prompt
report_template = PromptTemplate(
    input_variables=["research", "analysis"],
    template="""Based on the research: {research}

And the analysis: {analysis}

Write a comprehensive report on the impact of AI on software development. 
Include an introduction, main findings, and conclusion."""
)

# Format the prompt  
analysis_text = "\n".join([gen[0].message.content for gen in analysis_result.generations if gen and hasattr(gen[0], 'message')])
formatted_prompt = report_template.format(
    research=research_result.content,
    analysis=analysis_text
)

# Use generate_prompt method
prompt_values = [report_template.format_prompt(research=research_result.content, analysis=analysis_text)]
writing_result = writing_agent.generate_prompt(prompt_values)
# Check if it's a chat generation or regular generation
if hasattr(writing_result.generations[0][0], 'message'):
    original_report = writing_result.generations[0][0].message.content
    print(f"[Writing Agent] Report generated: {original_report[:100]}...")
else:
    original_report = writing_result.generations[0][0].text
    print(f"[Writing Agent] Report generated: {original_report[:100]}...")

# =============================================================================
# STEP 4: Review Agent - Uses BaseChatModel.generate with multiple conversations
# =============================================================================
print("\n[STEP 4] Review Agent reviewing report...")

# Create multiple review conversations
review_conversations = [
    [
        HumanMessage(content=f"Review this report for clarity and structure: {original_report[:500]}...")
    ],
    [
        HumanMessage(content=f"Check this report for technical accuracy: {original_report[:500]}...")
    ],
    [
        HumanMessage(content=f"Suggest improvements for this report: {original_report[:500]}...")
    ]
]

# Use generate method with multiple conversations
review_result = review_agent.generate(review_conversations)
print(f"[Review Agent] Generated {len(review_result.generations)} reviews")
for i, gen_list in enumerate(review_result.generations):
    if gen_list and hasattr(gen_list[0], 'message'):
        print(f"  Review {i+1}: {gen_list[0].message.content[:50]}...")

# =============================================================================
# STEP 5: Final Integration - Uses async methods
# =============================================================================
print("\n[STEP 5] Final integration using async methods...")

async def final_integration():
    """Demonstrate async LangChain methods"""
    
    # Collect all feedback
    reviews = []
    for gen_list in review_result.generations:
        if gen_list and hasattr(gen_list[0], 'message'):
            reviews.append(gen_list[0].message.content)
    
    review_summary = "\n".join(reviews)
    
    # Use ainvoke for final report
    final_messages = [
        SystemMessage(content="You are an editor. Integrate feedback into the final report."),
        HumanMessage(content=f"Original report: {original_report}\n\nReviews: {review_summary}\n\nCreate the final improved report.")
    ]
    
    print("[Final Integration] Using ainvoke...")
    final_result = await writing_agent.ainvoke(final_messages)
    print(f"[Final Report] {final_result.content[:100]}...")
    
    # Use BaseLanguageModel.generate with non-chat model for summaries
    summary_prompts = [
        f"Summarize this in one sentence: {final_result.content[:200]}",
        f"What is the key takeaway: {final_result.content[:200]}",
        f"Rate the importance 1-10: {final_result.content[:200]}"
    ]
    
    print("[Final Integration] Using BaseLanguageModel.generate...")
    summary_results = summary_agent.generate(summary_prompts)
    print(f"[Summary Agent] Generated {len(summary_results.generations)} summaries")
    for i, gen_list in enumerate(summary_results.generations):
        if gen_list and hasattr(gen_list[0], 'text'):
            print(f"  Summary {i+1}: {gen_list[0].text.strip()[:50]}...")
    
    # Use agenerate for multiple final tasks (needs List[List[BaseMessage]])
    final_task_conversations = [
        [HumanMessage(content="Create an executive summary of the final report")],
        [HumanMessage(content="List 3 action items from the report")], 
        [HumanMessage(content="Suggest 3 follow-up research questions")]
    ]
    
    print("[Final Integration] Using BaseChatModel.agenerate...")
    final_outputs = await analysis_agent.agenerate(final_task_conversations)
    print(f"[Final Tasks] Generated {len(final_outputs.generations)} final outputs")
    
    # Also demonstrate BaseLanguageModel.agenerate
    async_summary_prompts = [
        "Create a tweet-sized summary of this research",
        "What would be a good title for this report?",
        "List the top 3 benefits mentioned"
    ]
    
    print("[Final Integration] Using BaseLanguageModel.agenerate...")
    async_summaries = await summary_agent.agenerate(async_summary_prompts)
    print(f"[Async Summary] Generated {len(async_summaries.generations)} async summaries")
    
    return final_result, final_outputs, summary_results, async_summaries

# Run async integration
print("[user_program] Running async final integration...")
final_report, final_tasks, summaries, async_summaries = asyncio.run(final_integration())

# =============================================================================
# SUMMARY
# =============================================================================
print("\n" + "="*60)
print("LANGCHAIN MULTI-AGENT TEAM SUMMARY")
print("="*60)
print("Methods demonstrated:")
print("✓ BaseChatModel.invoke - Research Agent")
print("✓ BaseChatModel.generate - Analysis Agent (multi-conversation)")
print("✓ BaseLanguageModel.generate_prompt - Writing Agent (templates)")
print("✓ BaseChatModel.generate - Review Agent (multi-conversation)")
print("✓ BaseChatModel.ainvoke - Final integration (async)")
print("✓ BaseLanguageModel.generate - Summary Agent (batch prompts)")
print("✓ BaseChatModel.agenerate - Final tasks (async multi-conversation)")
print("✓ BaseLanguageModel.agenerate - Async summaries (async batch prompts)")
print("="*60)
print("[user_program] Multi-agent research pipeline completed successfully!")
print("="*60)