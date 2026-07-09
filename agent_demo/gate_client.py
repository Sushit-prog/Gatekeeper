"""Thin async HTTP client for the GateKeeper gate API."""

import httpx


class GateClient:
    """Async client for calling POST /gate/check."""

    def __init__(self, base_url: str = "http://localhost:8000") -> None:
        self._base_url = base_url
        self._client = httpx.AsyncClient(base_url=base_url, timeout=10.0)

    async def close(self) -> None:
        await self._client.aclose()

    async def check(
        self,
        session_id: str,
        tool_name: str,
        args: dict,
        agent_reasoning: str | None = None,
    ) -> dict:
        """Call POST /gate/check and return the full response dict.

        Returns:
            dict with keys: decision, matched_rules, latency_ms, audit_id, tags
        """
        payload = {
            "session_id": session_id,
            "tool_name": tool_name,
            "args": args,
        }
        if agent_reasoning:
            payload["agent_reasoning"] = agent_reasoning

        response = await self._client.post("/gate/check", json=payload)
        response.raise_for_status()
        return response.json()

    async def health(self) -> dict:
        response = await self._client.get("/health")
        response.raise_for_status()
        return response.json()
