import asyncio


async def main():
    from openai import AsyncOpenAI

    client = AsyncOpenAI()

    # Initialize conversation with system message
    messages = [{"role": "developer", "content": "You are a helpful assistant."}]

    # First turn
    user_input_1 = "What is the capital of France?"
    messages.append({"role": "user", "content": user_input_1})
    print(f"\nUser: {user_input_1}")

    completion_1 = await client.chat.completions.create(model="gpt-4o-mini", messages=messages)
    assistant_reply_1 = completion_1.choices[0].message.content
    messages.append({"role": "assistant", "content": assistant_reply_1})
    print(f"Assistant: {assistant_reply_1}")

    # Second turn
    user_input_2 = "What is the population of that city?"
    messages.append({"role": "user", "content": user_input_2})
    print(f"\nUser: {user_input_2}")

    completion_2 = await client.chat.completions.create(model="gpt-4o-mini", messages=messages)
    assistant_reply_2 = completion_2.choices[0].message.content
    messages.append({"role": "assistant", "content": assistant_reply_2})
    print(f"Assistant: {assistant_reply_2}")

    # Third turn
    user_input_3 = "Tell me about its most famous landmark."
    messages.append({"role": "user", "content": user_input_3})
    print(f"\nUser: {user_input_3}")

    completion_3 = await client.chat.completions.create(model="gpt-4o-mini", messages=messages)
    assistant_reply_3 = completion_3.choices[0].message.content
    messages.append({"role": "assistant", "content": assistant_reply_3})
    print(f"Assistant: {assistant_reply_3}")


if __name__ == "__main__":
    asyncio.run(main())
