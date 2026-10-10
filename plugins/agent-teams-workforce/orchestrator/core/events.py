"""The event channel remains separate from imported libraries' diagnostic stdout."""

from __future__ import annotations

import json
import sys
import threading
from typing import Protocol, TextIO, runtime_checkable

from typeguard import CollectionCheckStrategy, typechecked

from .io import JsonValue, json_object


@runtime_checkable
class EventSink(Protocol):
    """A typed event channel accepting named facts."""

    def __call__(self, event: str, **facts: JsonValue) -> None:
        """Accept an event name and its facts."""
        ...


class EventWriter:
    """Write complete JSON lines to the original stream, even during redirection."""

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def __init__(self, stream: TextIO | None = None) -> None:
        """Bind the original event stream and its line-write lock.

        Raises:
            TypeError: The stream cannot write and flush text events.

        """
        if stream is not None and (
            not callable(getattr(stream, "write", None)) or not callable(getattr(stream, "flush", None))
        ):
            message: str = "Event streams require write and flush methods"
            raise TypeError(message)
        self.stream: TextIO = stream if stream is not None else sys.stdout
        self.lock: threading.Lock = threading.Lock()

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def __call__(self, event: str, **facts: JsonValue) -> None:
        """Emit one validated JSON event without interleaving concurrent writers.

        Raises:
            TypeError: The event name is not text.

        """
        if not isinstance(event, str):
            message: str = "Event names must be strings"
            raise TypeError(message)
        payload: dict[str, JsonValue] = json_object({"event": event, **facts})
        with self.lock:
            self.stream.write(
                json.dumps(payload, ensure_ascii=False) + "\n",
            )
            self.stream.flush()
