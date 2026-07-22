"""Request/run correlation context with redacted diagnostics."""

from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="unassigned")
run_id_var: ContextVar[str] = ContextVar("run_id", default="unassigned")


def correlation() -> dict[str, str]:
    return {"request_id": request_id_var.get(), "run_id": run_id_var.get()}
