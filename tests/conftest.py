import pytest
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from app.main import app
from app.routers.quote import get_db_service
from app.routers.video import get_video_service


@pytest.fixture
def mock_db_service():
    service = MagicMock()
    service.search_quotes = AsyncMock(return_value=[])
    service.close = AsyncMock()
    return service


@pytest.fixture
def mock_video_service():
    service = MagicMock()
    service.read_to_stream = AsyncMock()
    service.get_thumbnail = AsyncMock()
    return service


@pytest.fixture
def client(mock_db_service, mock_video_service):
    app.dependency_overrides[get_db_service] = lambda: mock_db_service
    app.dependency_overrides[get_video_service] = lambda: mock_video_service
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
