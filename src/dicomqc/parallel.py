"""Bounded, deterministic helpers for per-file metadata work."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Iterable, Iterator
from concurrent.futures import Future, ProcessPoolExecutor, ThreadPoolExecutor
from itertools import chain
import multiprocessing
import os
import threading
import time
from typing import TypeVar

Input = TypeVar("Input")
Output = TypeVar("Output")


def _exit_when_parent_stops() -> None:
    """Ensure forcibly cancelled audits cannot leave pool workers behind."""
    parent = multiprocessing.parent_process()
    if parent is None:
        return

    def watch() -> None:
        while parent.is_alive():
            time.sleep(0.1)
        os._exit(1)

    threading.Thread(target=watch, name="dicomqc-parent-watch", daemon=True).start()


def _available_threads() -> int:
    try:
        return max(1, len(os.sched_getaffinity(0)))
    except (AttributeError, OSError):
        return max(1, os.cpu_count() or 1)


MAX_THREADS = _available_threads()
DEFAULT_THREADS = min(4, MAX_THREADS)


def validate_threads(value: int) -> int:
    """Validate a public thread count without accepting booleans as integers."""
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= MAX_THREADS:
        raise ValueError(f"Threads must be an integer between 1 and {MAX_THREADS}.")
    return value


def bounded_ordered_map(
    function: Callable[[Input], Output], values: Iterable[Input], *, threads: int,
) -> Iterator[Output]:
    """Map concurrently with bounded lookahead and input-order output."""
    threads = validate_threads(threads)
    if threads == 1:
        for value in values:
            yield function(value)
        return

    pending: deque[Future[Output]] = deque()
    iterator = iter(values)
    limit = threads * 2
    with ThreadPoolExecutor(max_workers=threads, thread_name_prefix="dicomqc-read") as executor:
        for _ in range(limit):
            try:
                pending.append(executor.submit(function, next(iterator)))
            except StopIteration:
                break
        while pending:
            yield pending.popleft().result()
            try:
                pending.append(executor.submit(function, next(iterator)))
            except StopIteration:
                pass


def bounded_ordered_process_map(
    function: Callable[[Input], Output], values: Iterable[Input], *, workers: int,
) -> Iterator[Output]:
    """Map batches across processes with bounded lookahead and input-order output."""
    workers = validate_threads(workers)
    if workers == 1:
        for value in values:
            yield function(value)
        return

    iterator = iter(values)
    limit = workers * 2
    initial = []
    exhausted = False
    for _ in range(limit + 1):
        try:
            initial.append(next(iterator))
        except StopIteration:
            exhausted = True
            break
    # Process startup and IPC cost more than they save for only a few batches.
    if exhausted:
        for value in initial:
            yield function(value)
        return

    pending: deque[Future[Output]] = deque()
    remaining = chain((initial.pop(),), iterator)
    with ProcessPoolExecutor(max_workers=workers, initializer=_exit_when_parent_stops) as executor:
        for value in initial:
            pending.append(executor.submit(function, value))
        while pending:
            yield pending.popleft().result()
            try:
                pending.append(executor.submit(function, next(remaining)))
            except StopIteration:
                pass
