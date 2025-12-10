class RPARuntimeError(RuntimeError):
    """Base RPA runtime error."""

class StepValidationError(RPARuntimeError):
    """Raised when step schema is invalid."""

class ActionExecutionError(RPARuntimeError):
    """Raised when an action fails to execute."""

class IncludeNotFoundError(RPARuntimeError):
    """Raised when an include file is missing."""
