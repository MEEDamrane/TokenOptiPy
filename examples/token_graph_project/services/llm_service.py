from pathlib import Path

SYSTEM_PROMPT = Path("prompts/system.txt").read_text(encoding="utf-8")

CLASSIFY_PROMPT = f"""
{SYSTEM_PROMPT}

Conversation history:
{{conversation_history}}

Customer message:
{{customer_message}}
"""


def classify_customer(client, conversation_history, customer_message):
    return client.chat.completions.create(
        model="local-model",
        prompt=CLASSIFY_PROMPT,
        messages=conversation_history,
    )
