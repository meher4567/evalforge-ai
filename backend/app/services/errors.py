class ResourceNotFoundError(ValueError):
    """A requested persisted entity does not exist."""


class InvalidRunRequestError(ValueError):
    """A run request is well-formed but its resources are incompatible."""


class DispatchError(RuntimeError):
    """A run was persisted but could not be submitted to the worker queue."""

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        super().__init__(f"Run {run_id} could not be dispatched")
