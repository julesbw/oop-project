"""Shared fixtures for the festival tests."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from deauville.api import create_app
from deauville.festival import Festival
from deauville.storage import JsonStorage

ROOT = Path(__file__).parents[1]
DATA_PATH = ROOT / "data" / "festival.json"


@pytest.fixture
def festival() -> Festival:
    """Load a fresh aggregate from the seed data."""
    return JsonStorage(DATA_PATH).load()


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    """Create an API backed by an isolated copy of the JSON file."""
    data_path = tmp_path / "festival.json"
    shutil.copyfile(DATA_PATH, data_path)
    return TestClient(create_app(JsonStorage(data_path)))
