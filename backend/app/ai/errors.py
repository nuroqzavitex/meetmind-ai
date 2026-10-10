"""Exception hierarchy for the AI core."""


class MeetMindError(Exception):
    """Base class for all MeetMind AI core errors."""


class TranscriptParseError(MeetMindError):
    """Raised when a transcript cannot be parsed."""


class LLMError(MeetMindError):
    """Raised when an LLM call fails."""


class LLMRefusal(LLMError):
    """Raised when the LLM refuses to answer a request."""


class AnalysisError(MeetMindError):
    """Raised when an analysis step fails.

    Attributes:
        step: Name of the analysis step that failed.
    """

    def __init__(self, message: str, *, step: str) -> None:
        super().__init__(message)
        self.step = step
