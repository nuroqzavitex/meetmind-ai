"""Enumerations for the AI core domain model."""

from enum import Enum


class Act(str, Enum):
    PROPOSE = "propose"; SUPPORT = "support"; OBJECT = "object"; AMEND = "amend"
    DECIDE = "decide"; REJECT = "reject"; DEFER = "defer"; REOPEN = "reopen"
    ASSIGN = "assign"; ACCEPT_TASK = "accept_task"
    RAISE_BLOCKER = "raise_blocker"; REQUEST = "request"; FEEDBACK = "feedback"
    KNOWLEDGE = "knowledge"; ASK = "ask"; HYPOTHETICAL = "hypothetical"


class ItemType(str, Enum):
    DECISION = "decision"; ACTION_ITEM = "action_item"; BLOCKER = "blocker"
    REQUEST = "request"; FEEDBACK = "feedback"; OPEN_QUESTION = "open_question"
    KNOWLEDGE = "knowledge"


class ItemStatus(str, Enum):
    FINAL = "final"; SUPERSEDED = "superseded"; REJECTED = "rejected"; OPEN = "open"


class ReviewState(str, Enum):
    PENDING = "pending"; APPROVED = "approved"; EDITED = "edited"; REJECTED = "rejected"


class OptState(str, Enum):
    PROPOSED = "proposed"; DISCUSSED = "discussed"; DECIDED = "decided"
    REJECTED = "rejected"; SUPERSEDED = "superseded"; OPEN = "open"
