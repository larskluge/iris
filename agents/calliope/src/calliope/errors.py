"""Friendly, typed errors so the REPL can surface clear messages (never a stack trace)."""


class CalliopeError(Exception):
    """Base for all Calliope-surfaced errors."""


class EmptyInputError(CalliopeError):
    """The user sent an empty/whitespace brief."""


class NoDraftError(CalliopeError):
    """An action (translate/accept) needs a current draft and there isn't one yet."""


class ModelUnavailableError(CalliopeError):
    """The local Ollama model server could not be reached or failed."""
