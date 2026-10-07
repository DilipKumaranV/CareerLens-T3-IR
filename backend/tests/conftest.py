import pytest
from fastapi.testclient import TestClient

from app.main import STATE, app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:      # builds the index once for the whole test session
        yield c


@pytest.fixture(scope="session")
def engine(client):
    return STATE["engine"]
