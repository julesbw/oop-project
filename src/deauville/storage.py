"""Replaceable storage implementations for the festival aggregate."""

from __future__ import annotations

import json
import os
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from .errors import FestivalError, StorageError
from .festival import Festival


class Storage(ABC):
    """Interface used by the CLI, API and tests."""

    @abstractmethod
    def load(self) -> Festival:
        """Load and validate a festival."""

    @abstractmethod
    def save(self, festival: Festival) -> None:
        """Persist a validated festival."""


class JsonStorage(Storage):
    """Read and write one festival document as JSON."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def load(self) -> Festival:
        """Load JSON and turn malformed data into a clear storage error."""
        try:
            with self.path.open(encoding="utf-8") as file:
                data: dict[str, Any] = json.load(file)
            return Festival.from_data(data)
        except FileNotFoundError as error:
            raise StorageError(f"Data file '{self.path}' was not found.") from error
        except json.JSONDecodeError as error:
            raise StorageError(
                f"Data file '{self.path}' is invalid JSON (line {error.lineno})."
            ) from error
        except FestivalError as error:
            raise StorageError(
                f"Data file '{self.path}' is invalid: {error}"
            ) from error
        except OSError as error:
            raise StorageError(f"Data file '{self.path}' cannot be read.") from error

    def save(self, festival: Festival) -> None:
        """Write atomically so a failed write cannot truncate the data file."""
        parent = self.path.parent
        temporary_path: str | None = None
        try:
            parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as file:
                temporary_path = file.name
                json.dump(festival.to_data(), file, ensure_ascii=False, indent=2)
                file.write("\n")
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary_path, self.path)
        except OSError as error:
            raise StorageError(f"Data file '{self.path}' cannot be written.") from error
        finally:
            if temporary_path is not None:
                try:
                    os.unlink(temporary_path)
                except FileNotFoundError:
                    pass


class MemoryStorage(Storage):
    """In-memory storage useful for isolated tests."""

    def __init__(self, festival: Festival | None = None) -> None:
        self._data = festival.to_data() if festival is not None else None

    def load(self) -> Festival:
        """Return a fresh aggregate from the saved in-memory document."""
        if self._data is None:
            raise StorageError("No festival is loaded.")
        return Festival.from_data(self._data)

    def save(self, festival: Festival) -> None:
        """Save a copy of the aggregate in memory."""
        self._data = festival.to_data()
