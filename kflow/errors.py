"""KFlow error types and error output formatting."""
import json
import sys


class KFlowError(Exception):
    """Base error for all expected KFlow failures."""
    exit_code: int = 1

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)

    def __str__(self):
        return self.message


class NodeExistsError(KFlowError):
    """A node with this name already exists."""
    def __init__(self, name: str):
        super().__init__(
            f"Node '{name}' already exists. Remove it first with: kflow remove {name} --force"
        )


class NodeNotFoundError(KFlowError):
    """Referenced node does not exist."""
    def __init__(self, name: str):
        super().__init__(f"Node '{name}' not found.")


class DerivationBlockedError(KFlowError):
    """Cannot delete a node that has downstream dependents."""
    def __init__(self, name: str, downstream: list[str]):
        downstream_list = ", ".join(downstream)
        super().__init__(
            f"Node '{name}' is referenced by downstream nodes: {downstream_list}. "
            f"Use --force to delete anyway."
        )


class ProjectAlreadyInitError(KFlowError):
    """Project already has .kflow/ directory."""
    def __init__(self, path: str):
        super().__init__(
            f"Project already initialized at '{path}'. .kflow/ already exists."
        )


class ProjectNotInitError(KFlowError):
    """No .kflow/ directory found."""
    def __init__(self):
        super().__init__(
            "Not a KFlow project. Run 'kflow init' first."
        )


class CyclicError(KFlowError):
    """Operation would create a cycle in the DAG."""
    def __init__(self, detail: str):
        super().__init__(f"Operation would create a cycle: {detail}")


class ValidationError(KFlowError):
    """User input validation failed."""
    def __init__(self, message: str):
        super().__init__(message)


def handle_error(e: KFlowError, json_output: bool = False) -> None:
    """Print error and exit with appropriate code."""
    if json_output:
        print(json.dumps({
            "ok": False,
            "error": str(e),
            "type": type(e).__name__,
        }))
    else:
        print(f"Error: {e}", file=sys.stderr)
    sys.exit(e.exit_code)
