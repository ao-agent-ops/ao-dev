from crewai import Agent, Task, Crew, Process, LLM
from crewai_tools import SerperDevTool


def main():
    llm = LLM(
        model="claude-sonnet-4-5",
        max_tokens=1024,
    )

    # Web search tool
    search_tool = SerperDevTool()

    # Create a researcher agent with web search
    researcher = Agent(
        role="Research Analyst",
        goal="Research topics using web search and provide factual information",
        backstory="You are an expert researcher who finds accurate, up-to-date information.",
        tools=[search_tool],
        llm=llm,
        verbose=True,
    )

    # Create a writer agent
    writer = Agent(
        role="Content Writer",
        goal="Transform research into clear, concise content",
        backstory="You are a skilled writer who creates engaging content from research.",
        llm=llm,
        verbose=True,
    )

    # Task 1: Research task
    research_task = Task(
        description="Search the web to find out what 'The Hitchhiker's Guide to the Galaxy' says about the number 42.",
        expected_output="A brief explanation of the significance of 42 in the book.",
        agent=researcher,
    )

    # Task 2: Writing task (uses output from research)
    writing_task = Task(
        description="Take the research and write a single tweet about it.",
        expected_output="A single tweet (under 280 characters) about the significance of 42.",
        agent=writer,
    )

    # Create crew with sequential process
    crew = Crew(
        agents=[researcher, writer],
        tasks=[research_task, writing_task],
        process=Process.sequential,
        verbose=True,
    )

    # Execute the crew
    result = crew.kickoff()
    print(f"Final result: {result}")


if __name__ == "__main__":
    main()
