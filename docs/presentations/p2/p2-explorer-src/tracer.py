"""Record what our own code does while it runs: every line, in order, with the local variables.

Python lets a program install a trace function (sys.settrace for the current thread, threading.settrace for
threads started later). Python calls it with event "call" when any function starts; if it returns a second,
"local" function, that one is called for every "line", "exception" and "return" in that function.
We return a local function only for our own files, so FastAPI, Starlette, Pydantic and httpx2 run untraced.

This module knows nothing about AgroPilot. build_explorer.py uses it.
"""

import dataclasses
import sys
import threading
from datetime import date, datetime
from fractions import Fraction
from uuid import UUID

MAX_TEXT = 160


def show_fraction(value: Fraction) -> str:
    """An exact Fraction as text: "29.75" when it is a finite decimal, "5000/3 (≈1666.667)" when it is not."""
    if value.denominator == 1:
        return str(value.numerator)
    rest = value.denominator
    for factor in (2, 5):
        while rest % factor == 0:
            rest //= factor
    if rest != 1:  # 1/3, 5000/3, ...: no finite decimal exists, so show the fraction and an approximation
        return f"{value.numerator}/{value.denominator} (≈{float(value):.3f})"
    places, scaled = 0, abs(value)
    while scaled.denominator != 1:
        scaled *= 10
        places += 1
    digits = str(scaled.numerator).rjust(places + 1, "0")
    sign = "-" if value < 0 else ""
    return f"{sign}{digits[:-places]}.{digits[-places:]}"


def show(value) -> str:
    """A short, stable text for a value, as a debugger's variables panel would show it."""
    if isinstance(value, Fraction):
        text = show_fraction(value)
    elif isinstance(value, (date, datetime)):
        text = value.isoformat()
    elif isinstance(value, UUID):
        text = str(value)
    elif dataclasses.is_dataclass(value) and not isinstance(value, type):
        fields = ", ".join(f"{field.name}={show(getattr(value, field.name))}" for field in dataclasses.fields(value))
        text = f"{type(value).__name__}({fields})"
    elif isinstance(value, (list, tuple)) and len(value) > 3:
        text = f"[{show(value[0])}, … {len(value)} items]"
    elif isinstance(value, (list, tuple)):
        text = "[" + ", ".join(show(item) for item in value) + "]"
    else:
        text = repr(value)
        if " at 0x" in text:  # "<starlette.requests.Request object at 0x10...>": the address changes every run
            text = f"<{type(value).__name__}>"
    return text if len(text) <= MAX_TEXT else text[: MAX_TEXT - 1] + "…"


def thread_kind(name: str) -> str:
    if name.startswith("AnyIO worker"):
        return "worker"  # FastAPI runs a plain `def` endpoint in a worker thread
    if name.startswith("asyncio-portal"):
        return "event-loop"  # TestClient's event loop: middleware, async exception handlers
    return name


class Recorder:
    """Records line, exception and return events in the given files, while `active` is true.

    For each function call (a frame) it keeps the file, the function, the calling frame and the thread.
    For each event it keeps only the local variables that changed since that frame's previous event,
    as text for the page, and as the real objects (`raw`) for the build's own checks.
    """

    def __init__(self, files: dict[str, str]) -> None:
        self.files = files  # absolute path -> short name shown on the page, e.g. "routers/plan.py"
        self.active = False
        self._lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        self.frames: list[dict] = []
        self.events: list[dict] = []
        self._numbers: dict = {}  # frame object -> its index in self.frames
        self._last: dict[int, dict[str, str]] = {}  # frame index -> the locals shown at its previous event

    def install(self) -> None:
        threading.settrace(self._on_call)  # threads started from now on
        sys.settrace(self._on_call)  # this thread

    def uninstall(self) -> None:
        threading.settrace(None)
        sys.settrace(None)

    def _on_call(self, frame, event, arg):
        if not self.active or frame.f_code.co_filename not in self.files:
            return None  # not ours: run it untraced
        return self._on_event

    def _on_event(self, frame, event, arg):
        if not self.active or event not in ("line", "exception", "return"):
            return self._on_event
        if event == "exception" and arg[0] in (GeneratorExit, StopIteration):
            return self._on_event  # how Python ends a generator (any() stops early), not an error in our code
        with self._lock:
            number = self._frame_number(frame)
            shown_now = {}
            raw_changed = {}
            for name, value in frame.f_locals.items():
                if name.startswith("__"):
                    continue
                shown_now[name] = show(value)
                if self._last.get(number, {}).get(name) != shown_now[name]:
                    raw_changed[name] = value
            self._last[number] = shown_now
            record = {
                "frame": number,
                "line": frame.f_lineno,
                "event": event,
                "changed": {name: shown_now[name] for name in raw_changed},
                "raw": raw_changed,  # the build's checks only; never written to the page
            }
            if event == "exception":
                record["detail"] = show(arg[1]) if str(arg[1]) else arg[0].__name__
                record["exception"] = arg[0].__name__
            elif event == "return":
                record["detail"] = show(arg)
                record["raw_return"] = arg
            self.events.append(record)
        return self._on_event

    def _frame_number(self, frame) -> int:
        if frame not in self._numbers:
            parent = frame.f_back
            while parent is not None and parent not in self._numbers:
                parent = parent.f_back  # skip framework frames between two of ours
            self._numbers[frame] = len(self.frames)
            self.frames.append(
                {
                    "file": self.files[frame.f_code.co_filename],
                    "function": frame.f_code.co_name,
                    "parent": self._numbers[parent] if parent is not None else None,
                    "thread": thread_kind(threading.current_thread().name),
                }
            )
        return self._numbers[frame]
