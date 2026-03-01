import pytest


@pytest.fixture
def engine():
    """No-op override — unit tests don't need the database."""
    yield None


@pytest.fixture(autouse=True)
def cleanup():
    """No-op override — unit tests don't need DB cleanup."""
    yield
