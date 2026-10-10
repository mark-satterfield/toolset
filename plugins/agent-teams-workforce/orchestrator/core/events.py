"""The event channel remains separate from imported libraries' diagnostic stdout."""

from __future__ import annotations

import json
import sys
import threading
from typing import TextIO

from typeguard import CollectionCheckStrategy, typechecked

from .io import json_object


class EventWriter:
    """Write complete JSON lines to the original stream, even during redirection."""

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def __init__(self, stream: TextIO | None = None) -> None:
        """Bind the original event stream and its line-write lock."""
        self.stream = stream if stream is not None else sys.stdout
        self.lock = threading.Lock()

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def __call__(self, event: str, **facts: object) -> None:
        """Emit one validated JSON event without interleaving concurrent writers."""
        payload = json_object({"event": event, **facts})
        with self.lock:
            self.stream.write(
                json.dumps(payload, ensure_ascii=False) + "\n",
            )
            self.stream.flush()
