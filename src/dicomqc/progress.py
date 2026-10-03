"""Optional value-free progress events shared by the CLI engine and API."""

from typing import Callable

Progress = Callable[[dict], None]


def emit(callback: Progress | None, phase: str, completed: int = 0, total: int | None = None) -> None:
    if callback is not None:
        callback({"phase": phase, "completed": completed, "total": total})
