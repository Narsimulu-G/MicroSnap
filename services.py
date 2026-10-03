"""Adapters for Gemini requests and WhatsApp messages."""

import json

from google.genai import types

from core import clean_summary, normalize_phone
from prompts import SUMMARY_REQUEST_PROMPT, SYSTEM_PROMPT


def make_content(text: str, image: bytes | None = None, mime: str | None = None):
    """Build one Gemini user message from optional text and an image."""
    parts = []
    if image:
        parts.append(types.Part.from_bytes(data=image, mime_type=mime))

    prompt = text or "Identify this meal and estimate calories and macros."
    parts.append(types.Part.from_text(text=prompt))
    return types.Content(role="user", parts=parts)


def generate_reply(client, model: str, history: list, content):
    """Generate a chat response without mutating the caller's history."""
    response = client.models.generate_content(
        model=model,
        contents=[*history, content],
        config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
    )
    if not response.text or not response.text.strip():
        raise ValueError("The model returned an empty response.")

    # Keep the original model message so any provider metadata is preserved.
    model_content = response.candidates[0].content
    return response.text.strip(), model_content


def generate_summary(client, model: str, history: list) -> str:
    """Summarize the conversation without changing its chat history."""
    response = client.models.generate_content(
        model=model,
        contents=[*history, make_content(SUMMARY_REQUEST_PROMPT)],
        config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
    )
    return clean_summary(response.text)


def send_whatsapp(
    client,
    sender: str,
    recipient: str,
    name: str,
    summary: str,
    mode: str = "session",
    content_sid: str = "",
):
    """Submit a summary once; callers must handle uncertain delivery safely."""
    summary = clean_summary(summary)
    sender_number = normalize_phone(sender.removeprefix("whatsapp:"))
    recipient_number = normalize_phone(recipient)
    message = {
        "from_": f"whatsapp:{sender_number}",
        "to": f"whatsapp:{recipient_number}",
    }

    if mode == "template":
        if not content_sid.startswith("HX"):
            raise ValueError("An approved Content SID starting with HX is required.")
        message.update(
            content_sid=content_sid,
            content_variables=json.dumps({"1": name, "2": summary}, ensure_ascii=False),
        )
    elif mode == "session":
        message["body"] = f"Hi {name}! Your MacroSnap summary:\n\n{summary}"
    else:
        raise ValueError("WHATSAPP_MODE must be session or template.")

    # Do not automatically retry: Twilio may accept a request before a timeout.
    return client.messages.create(**message)
