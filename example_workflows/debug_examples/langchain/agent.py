from langchain.agents import create_agent


def get_weather(city: str) -> str:
    """Get weather for a given city."""
    return f"It's always sunny in {city}!"


def main():
    agent = create_agent(
        model="claude-sonnet-4-5-20250929",
        tools=[get_weather],
        system_prompt="You are a helpful assistant",
    )

    # Run the agent
    result = agent.invoke(
        {"messages": [{"role": "user", "content": "what is the weather in sf"}]}
    )
    print(result)


if __name__ == "__main__":
    main()
