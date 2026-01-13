from crewai import Agent, Task, Crew, Process, LLM
from crewai_tools import JinaScrapeWebsiteTool


def main():
    llm = LLM(
        model="claude-sonnet-4-5",
        max_tokens=1024,
    )

    # Jina scrape tool - converts web pages to markdown
    scrape_tool = JinaScrapeWebsiteTool()

    # Create a scraper agent
    scraper = Agent(
        role="Web Scraper",
        goal="Scrape web pages and extract their content",
        backstory="You are an expert at extracting useful information from websites.",
        tools=[scrape_tool],
        llm=llm,
        verbose=True,
    )

    # Create a summarizer agent
    summarizer = Agent(
        role="Content Summarizer",
        goal="Summarize scraped content into concise summaries",
        backstory="You are skilled at distilling complex information into key points.",
        llm=llm,
        verbose=True,
    )

    # Task 1: Scrape a simple webpage
    scrape_task = Task(
        description="Scrape the webpage at https://www.crewai.com/ and extract its content.",
        expected_output="The full text content of the webpage.",
        agent=scraper,
    )

    # Task 2: Summarize the scraped content
    summarize_task = Task(
        description="Summarize the scraped content in one sentence.",
        expected_output="A single sentence summary of the webpage content.",
        agent=summarizer,
    )

    # Create crew with sequential process
    crew = Crew(
        agents=[scraper, summarizer],
        tasks=[scrape_task, summarize_task],
        process=Process.sequential,
        verbose=True,
    )

    # Execute the crew
    result = crew.kickoff()
    print(f"Final result: {result}")


if __name__ == "__main__":
    main()
