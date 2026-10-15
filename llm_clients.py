"""
Thin wrapper around Groq and Gemini so any node can call call_llm(...)
without caring which provider is behind it. Swap models per node via .env.
"""
import os
import json
from groq import Groq
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

_groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

GROQ_MODEL = "llama-3.3-70b-versatile"
GEMINI_MODEL = "gemini-3.5-flash"


def call_groq(prompt: str, json_mode: bool = False) -> str:
    kwargs = {}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = _groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        **kwargs,
    )
    return response.choices[0].message.content


def call_gemini(prompt: str, json_mode: bool = False) -> str:
    generation_config = {}
    if json_mode:
        generation_config["response_mime_type"] = "application/json"

    model = genai.GenerativeModel(GEMINI_MODEL, generation_config=generation_config)
    response = model.generate_content(prompt)
    return response.text


def call_llm(prompt: str, provider: str = "groq", json_mode: bool = False) -> str:
    """Single entry point every node should use."""
    if provider == "groq":
        return call_groq(prompt, json_mode=json_mode)
    elif provider == "gemini":
        return call_gemini(prompt, json_mode=json_mode)
    raise ValueError(f"Unknown provider: {provider}")


def call_llm_json(prompt: str, provider: str = "groq") -> dict:
    """Call the LLM and parse the JSON response, with a clear error if it fails."""
    raw = call_llm(prompt, provider=provider, json_mode=True)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM did not return valid JSON: {raw[:300]}") from e
