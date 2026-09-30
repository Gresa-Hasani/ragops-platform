"""Integration test fixtures.

These tests talk to real PostgreSQL and Qdrant instances (``docker compose up -d
postgres qdrant``). They are deselected by default and run with ``pytest -m
integration``. If the services are not reachable the tests fail rather than skip, so a
green run always means the infrastructure was actually exercised.
"""

import os

import pytest

DEFAULT_TEST_DATABASE_URL = "postgresql+asyncpg://ragops:ragops@localhost:5442/ragops_test"
DEFAULT_TEST_QDRANT_URL = "http://localhost:6333"


@pytest.fixture(scope="session")
def test_database_url() -> str:
    return os.environ.get("RAGOPS_TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)


@pytest.fixture(scope="session")
def test_qdrant_url() -> str:
    return os.environ.get("RAGOPS_TEST_QDRANT_URL", DEFAULT_TEST_QDRANT_URL)
