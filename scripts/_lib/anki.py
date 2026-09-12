"""Minimal AnkiConnect client (API version 6)."""

import requests

from .errors import AnkiError

DEFAULT_URL = "http://127.0.0.1:8765"

__all__ = ["DEFAULT_URL", "AnkiConnect", "AnkiError"]


class AnkiConnect:
    def __init__(self, url: str = DEFAULT_URL):
        self.url = url

    def invoke(self, action: str, **params):
        try:
            resp = requests.post(self.url, json={"action": action, "version": 6, "params": params}, timeout=60)
        except requests.ConnectionError as exc:
            raise AnkiError(f"cannot reach AnkiConnect at {self.url}; is Anki running?") from exc
        resp.raise_for_status()
        body = resp.json()
        if body.get("error"):
            raise AnkiError(f"{action}: {body['error']}")
        return body["result"]

    def multi(self, actions: list[dict]) -> list[tuple[object, str | None]]:
        """Run many actions in one request; returns (result, error) per action."""
        results = self.invoke("multi", actions=[{**action, "version": 6} for action in actions])
        return [(r.get("result"), r.get("error")) for r in results]
