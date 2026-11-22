"""JSON chat clients for one hosted API and a local Ollama installation."""

from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def make_client(backend: str, model: str, api_key: str = ""):
    """Return a callable taking (system, prompt) and yielding a parsed JSON object."""
    if backend not in ("OpenAI", "Ollama"):
        raise ValueError("Choose OpenAI or Ollama.")
    if not isinstance(model, str) or not model.strip():
        raise ValueError("Enter the model name.")
    model = model.strip()
    hosted = backend == "OpenAI"
    headers = {"Content-Type": "application/json"}
    if hosted:
        key = (api_key or os.environ.get("OPENAI_API_KEY", "")).strip()
        if not key:
            raise ValueError("Set OPENAI_API_KEY or enter your OpenAI API key in the app.")
        headers["Authorization"] = f"Bearer {key}"
        url = "https://api.openai.com/v1/chat/completions"
    else:
        url = "http://127.0.0.1:11434/api/chat"

    def complete(system: str, prompt: str) -> dict:
        payload = {"model": model, "messages": [{"role": "system", "content": system},
                                                 {"role": "user", "content": prompt}]}
        if hosted:
            payload["response_format"] = {"type": "json_object"}
            payload["store"] = False
        else:
            payload.update({"format": "json", "stream": False})
        request = Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
        try:
            with urlopen(request, timeout=120) as response:
                envelope = json.load(response)
        except HTTPError as exc:
            hints = {
                400: "Check that the model accepts JSON chat requests.",
                401: "Check your API key.",
                403: "Check model access for your API project.",
                404: "Check the model name and that it is available.",
                429: "Check your API quota or retry later.",
            }
            if not hosted and exc.code == 404:
                hints[404] = "Download the selected model with ollama pull, then retry."
            hint = hints.get(exc.code, "Try the request again later.")
            # Provider error bodies can contain user input. Display only the status.
            raise RuntimeError(f"{backend} returned HTTP {exc.code}. {hint}") from None
        except (URLError, OSError):
            hint = ("Check your internet connection." if hosted
                    else "Start Ollama on this computer and check that its local server is running.")
            raise RuntimeError(f"{backend} could not be reached or timed out. {hint}") from None
        except (UnicodeError, json.JSONDecodeError):
            raise RuntimeError(f"{backend} returned an unreadable response.") from None
        try:
            message = envelope["choices"][0]["message"] if hosted else envelope["message"]
            if message.get("refusal"):
                raise RuntimeError(f"{backend} declined the request. Review the input.")
            result = json.loads(message["content"])
        except (KeyError, TypeError, IndexError, AttributeError, json.JSONDecodeError):
            raise ValueError("The model did not return a JSON object.") from None
        if not isinstance(result, dict):
            raise ValueError("The model did not return a JSON object.")
        return result

    return complete
