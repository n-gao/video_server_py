from unittest.mock import AsyncMock

from app.models import Episode, QuoteResult


class TestSearchEndpoint:
    def test_returns_results(self, client, mock_db_service):
        qr = QuoteResult.model_validate({
            "episode": "s01e05",
            "person": "Bob",
            "text": "Hello",
            "timestamp": 10.5,
            "MatchingScore": 1.0,
        })
        mock_db_service.search_quotes = AsyncMock(return_value=[qr])

        resp = client.get("/api/search", params={"query": "hello"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["person"] == "Bob"
        assert data[0]["season"] == 1

    def test_missing_query_returns_422(self, client):
        resp = client.get("/api/search")
        assert resp.status_code == 422

    def test_num_results_clamped_low(self, client, mock_db_service):
        mock_db_service.search_quotes = AsyncMock(return_value=[])
        client.get("/api/search", params={"query": "x", "numResults": 0})
        # search_quotes(query, num_results) — positional args
        assert mock_db_service.search_quotes.call_args[0][1] == 1

    def test_num_results_clamped_high(self, client, mock_db_service):
        mock_db_service.search_quotes = AsyncMock(return_value=[])
        client.get("/api/search", params={"query": "x", "numResults": 100})
        assert mock_db_service.search_quotes.call_args[0][1] == 20


class TestVideoEndpoint:
    def test_returns_video(self, client, mock_video_service, tmp_path):
        video_file = tmp_path / "clip.mp4"
        video_file.write_bytes(b"fake_video_data")
        mock_video_service.read_to_stream = AsyncMock(return_value=str(video_file))

        resp = client.get("/api/video/1/5", params={"start": 10, "duration": 20})
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "video/mp4"
        assert resp.content == b"fake_video_data"


class TestThumbnailEndpoint:
    def test_returns_thumbnail(self, client, mock_video_service, tmp_path):
        thumb_file = tmp_path / "thumb.jpg"
        thumb_file.write_bytes(b"fake_jpeg_data")
        mock_video_service.get_thumbnail = AsyncMock(return_value=str(thumb_file))

        resp = client.get("/api/thumbnail/1/5", params={"timestamp": 2})
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/jpeg"
        assert resp.content == b"fake_jpeg_data"
