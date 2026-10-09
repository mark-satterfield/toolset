"""The event channel remains separate from imported libraries' diagnostic stdout."""

from __future__ import annotations

import json
import sys
import threading
from typing import Any, TextIO


class EventWriter:
    """Write complete JSON lines to the original stream, even during redirection."""

    def __init__(self, stream: TextIO | None = None) -> None:
        self.stream = stream if stream is not None else sys.stdout
        self.lock = threading.Lock()

    def __call__(self, event: str, **facts: Any) -> None:
        with self.lock:
            self.stream.write(
                json.dumps({"event": event, **facts}, ensure_ascii=False) + "\n"
            )
            self.stream.flush()
