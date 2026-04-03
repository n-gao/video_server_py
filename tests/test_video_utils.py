import hashlib

from app.services.video_service import sha256_hash
from app.routers.video import get_file_path


class TestSha256Hash:
    def test_deterministic(self):
        assert sha256_hash("hello") == sha256_hash("hello")

    def test_known_digest(self):
        expected = hashlib.sha256(b"test").hexdigest()
        assert sha256_hash("test") == expected

    def test_empty_string(self):
        expected = hashlib.sha256(b"").hexdigest()
        assert sha256_hash("") == expected

    def test_different_inputs_differ(self):
        assert sha256_hash("a") != sha256_hash("b")


class TestGetFilePath:
    def test_single_episode(self):
        path = get_file_path(1, "5")
        assert path == "videos/s01/s01e05.mp4"

    def test_double_digit_episode(self):
        path = get_file_path(2, "12")
        assert path == "videos/s02/s02e12.mp4"

    def test_multi_part_episode(self):
        path = get_file_path(5, "10a")
        assert path == "videos/s05/s05e10a.mp4"

    def test_multi_part_episode_b(self):
        path = get_file_path(1, "3b")
        assert path == "videos/s01/s01e03b.mp4"

    def test_season_padding(self):
        path = get_file_path(99, "1")
        assert path == "videos/s99/s99e01.mp4"
