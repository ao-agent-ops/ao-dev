import asyncio
from langchain.agents import create_agent


def get_weather(city: str) -> str:
    """Get weather for a given city."""
    return f"It's always sunny in {city}!"


def multiply(a: int, b: int) -> int:
    """Multiply two numbers."""
    return a * b


def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


async def main():
    agent = create_agent(
        model="claude-sonnet-4-5-20250929",
        tools=[get_weather, multiply, add],
        system_prompt="You are a helpful assistant.",
    )

    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": "What is 7 * 8, then add 5? Also what's the weather in SF?"}]}
    )
    print(result)


if __name__ == "__main__":
    asyncio.run(main())