from openai import OpenAI


client = OpenAI()

# Initialize conversation with system message
messages = [{"role": "developer", "content": "You are a helpful assistant."}]

user_input = "Pretend you are having a conversation, taking turns between a human and an AI. You start by being the human and you ask a question. Then you STOP. I will keep feeding the conversation back to you and you just take ONE turn. Keep each turn SHORT."

# Add user message to conversation
messages.append({"role": "user", "content": user_input})

for i in range(5):
    # Get response from OpenAI
    completion = client.chat.completions.create(model="gpt-4o-mini", messages=messages)
    assistant_reply = completion.choices[0].message.content
    messages.append({"role": "assistant", "content": assistant_reply})
