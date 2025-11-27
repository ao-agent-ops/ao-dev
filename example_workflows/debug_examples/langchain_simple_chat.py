from langchain.chat_models import init_chat_model

model = init_chat_model("gpt-5.1")
response = model.invoke("Why do parrots talk? Keep it short.")

prompt2 = f"Summarize the following. Keep it short.\n\n{response.content}"
response2 = model.invoke(prompt2)

print(response2.content)