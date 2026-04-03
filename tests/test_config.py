from app.config import DatabaseSettings, CacheSettings, VideoSettings


class TestDatabaseSettings:
    def test_defaults(self):
        s = DatabaseSettings()
        assert s.connection_string == "mongodb://localhost:27017"
        assert s.database_name == "video_server"
        assert s.quote_collection_name == "quotes"
        assert s.episode_collection_name == "episodes"

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("VS_DB_CONNECTION_STRING", "mongodb://remote:27017")
        monkeypatch.setenv("VS_DB_DATABASE_NAME", "test_db")
        s = DatabaseSettings()
        assert s.connection_string == "mongodb://remote:27017"
        assert s.database_name == "test_db"


class TestCacheSettings:
    def test_defaults(self):
        s = CacheSettings()
        assert s.folder == ".cache"
        assert s.size == 1000

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("VS_CACHE_FOLDER", "/tmp/test_cache")
        monkeypatch.setenv("VS_CACHE_SIZE", "50")
        s = CacheSettings()
        assert s.folder == "/tmp/test_cache"
        assert s.size == 50


class TestVideoSettings:
    def test_defaults(self):
        s = VideoSettings()
        assert s.folder == "./videos"
        assert s.format == ".mp4"

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("VS_VIDEO_FOLDER", "/data/videos")
        monkeypatch.setenv("VS_VIDEO_FORMAT", ".mkv")
        s = VideoSettings()
        assert s.folder == "/data/videos"
        assert s.format == ".mkv"
