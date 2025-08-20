import requests
from typing import Any

class LMClient:
    """
    Simple wrapper for the local LM‑Studio HTTP endpoint.
    Adjust `host` and `port` to match your setup.
    """


    def __init__(self, host: str = "http://127.0.0.1", port: int = 1234):
        self.url = f"{host}:{port}/v1/chat/completions"

    def ask(self, prompt: str) -> str:
        """Send a prompt and return the model’s raw text answer."""
        payload = {
            "model": "openai/gpt-oss-20b",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.9,
            "max_tokens": 12000,           # plenty for large HTML snippets
        }
        resp = requests.post(self.url, json=payload, timeout=300)
        resp.raise_for_status()
        data: Any = resp.json()
        return data["choices"][0]["message"]["content"]
