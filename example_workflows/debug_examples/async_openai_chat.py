import asyncio


async def main():
    from openai import AsyncOpenAI

    client = AsyncOpenAI()

    # Initialize conversation with system message
    messages = [{"role": "developer", "content": "You are a helpful assistant."}]

    # Get user input
    user_input = "hello hello"

    # Add user message to conversation
    messages.append({"role": "user", "content": user_input})

    try:
        # Get response from OpenAI
        completion = await client.chat.completions.create(model="gpt-5-nano", messages=messages)

        assistant_reply = completion.choices[0].message.content
        messages.append({"role": "assistant", "content": assistant_reply})

        print(f"\nAssistant: {assistant_reply}")

    except Exception as e:
        print(f"Error: {e}")
        # Remove the user message if there was an error
        messages.pop()


if __name__ == "__main__":
    asyncio.run(main())
