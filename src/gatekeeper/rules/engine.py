from abc import ABC, abstractmethod

from gatekeeper.models.requests import GateDecision
from gatekeeper.rules.base import SessionStateRecord


class RuleEngine(ABC):
    """Abstract interface for rule engine implementations.

    Both PydanticRuleEngine and OPARuleEngine implement this interface,
    allowing the API layer to swap backends via ENGINE_BACKEND env var.
    """

    @abstractmethod
    async def evaluate(
        self,
        tool_name: str,
        args: dict,
        session_history: list[SessionStateRecord],
    ) -> GateDecision:
        """Evaluate a tool call against all applicable rules.

        Args:
            tool_name: The name of the tool being invoked.
            args: The arguments dict for the tool call.
            session_history: Pre-fetched session history for stateful rules.

        Returns:
            GateDecision with decision, matched_rules, latency_ms, tags.
        """
        ...
