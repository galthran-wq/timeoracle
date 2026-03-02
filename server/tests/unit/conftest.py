import pytest


@pytest.fixture
def engine():
    yield None


@pytest.fixture(autouse=True)
def cleanup():
    yield
