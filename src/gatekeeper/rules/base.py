from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from gatekeeper.models.requests import RuleResult


class SessionStateRecord(BaseModel):
    """Lightweight record for session history passed to stateful rules."""

    session_id: str
    tool_name: str
    args: dict[str, Any]
    decision: str
    tags: dict[str, Any] | None = None
    created_at: datetime


class Rule(ABC):
    """Base class for all policy rules.

    Rules evaluate tool_name + args ONLY. The agent_reasoning field is
    deliberately excluded from the signature to enforce structural isolation
    — no rule can ever access the agent's stated justification.
    """

    rule_id: str
    applies_to: list[str]  # ["*"] means all tools

    @abstractmethod
    def evaluate(self, tool_name: str, args: dict) -> RuleResult:
        """Evaluate this rule against the given tool call.

        Args:
            tool_name: The name of the tool being invoked.
            args: The arguments dict for the tool call.

        Returns:
            RuleResult indicating pass/fail, reason, and severity.
        """
        ...


class StatefulRule(ABC):
    """Base class for stateful cross-call constraint rules.

    Stateful rules receive session history (pre-fetched, read-only) and can
    make decisions based on prior calls in the same session. Like Rule, the
    agent_reasoning field is deliberately excluded from the signature.
    """

    rule_id: str
    applies_to: list[str]  # ["*"] means all tools

    @abstractmethod
    async def evaluate(
        self,
        tool_name: str,
        args: dict,
        session_id: str,
        session_history: list[SessionStateRecord],
    ) -> RuleResult:
        """Evaluate this rule against the current call and session history.

        Args:
            tool_name: The name of the tool being invoked.
            args: The arguments dict for the tool call.
            session_id: The current session ID.
            session_history: Pre-fetched list of prior session_state records
                for this (session_id, tool_name) pair, ordered by created_at.

        Returns:
            RuleResult with rule_type="stateful".
        """
        ...
