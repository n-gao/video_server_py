import os
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path

import pytest

from app.config import CacheSettings
from app.services.video_service import VideoService


@pytest.fixture
def cache_dir(tmp_path):
    return tmp_path / "cache"


@pytest.fixture
def service(cache_dir):
    settings = CacheSettings.model_construct(folder=str(cache_dir), size=5)
    return VideoService(settings)


class TestCheckCacheSize:
    def test_creates_dir_if_missing(self, service, cache_dir):
        assert not cache_dir.exists()
        service._check_cache_size()
        assert cache_dir.exists()

    def test_no_eviction_under_limit(self, service, cache_dir):
        cache_dir.mkdir(parents=True)
        for i in range(3):
            (cache_dir / f"file{i}.mp4").touch()
        service._check_cache_size()
        assert len(list(cache_dir.iterdir())) == 3

    def test_evicts_oldest_when_over_limit(self, service, cache_dir):
        cache_dir.mkdir(parents=True)
        # Create 7 files (limit is 5), with staggered access times
        for i in range(7):
            f = cache_dir / f"file{i}.mp4"
            f.touch()
            os.utime(f, (i, i))

        service._check_cache_size()
        remaining = {f.name for f in cache_dir.iterdir()}
        # Oldest 2 (file0, file1) should be evicted
        assert "file0.mp4" not in remaining
        assert "file1.mp4" not in remaining
        assert len(remaining) == 5


class TestGetSegment:
    @pytest.mark.asyncio
    async def test_cache_hit(self, service, cache_dir):
        cache_dir.mkdir(parents=True)
        # Pre-create the expected cache file
        from app.services.video_service import sha256_hash

        expected_name = f"{sha256_hash('video.mp4')}_{10.0}_{20.0}.mp4"
        expected_path = cache_dir / expected_name
        expected_path.write_bytes(b"cached")

        result = await service._get_segment("video.mp4", 10.0, 20.0)
        assert result == str(expected_path)

    @pytest.mark.asyncio
    async def test_generates_and_caches(self, service, cache_dir):
        cache_dir.mkdir(parents=True)

        async def fake_ffmpeg(*args, **kwargs):
            proc = MagicMock()
            proc.wait = AsyncMock()
            proc.returncode = 0

            # Simulate FFmpeg creating segment files in the temp dir
            cmd = args
            for i, arg in enumerate(cmd):
                if str(arg).endswith("seg%03d.mp4"):
                    seg_dir = Path(arg).parent
                    (seg_dir / "seg000.mp4").write_bytes(b"pre-roll")
                    (seg_dir / "seg001.mp4").write_bytes(b"part1")
                    (seg_dir / "seg002.mp4").write_bytes(b"part2")
                    break
                if arg == "concat":
                    # Second FFmpeg call: create the output file
                    output_path = Path(cmd[-1])
                    output_path.write_bytes(b"final")
                    break

            return proc

        with patch("asyncio.create_subprocess_exec", side_effect=fake_ffmpeg):
            result = await service._get_segment("video.mp4", 10.0, 20.0)

        assert Path(result).exists()
        # Temp folder should be cleaned up — only cache files remain
        entries = list(cache_dir.iterdir())
        assert all(e.is_file() for e in entries)

    @pytest.mark.asyncio
    async def test_cleans_up_temp_on_error(self, service, cache_dir):
        cache_dir.mkdir(parents=True)

        async def failing_ffmpeg(*args, **kwargs):
            proc = MagicMock()
            proc.wait = AsyncMock(side_effect=RuntimeError("boom"))
            return proc

        with patch("asyncio.create_subprocess_exec", side_effect=failing_ffmpeg):
            with pytest.raises(RuntimeError):
                await service._get_segment("video.mp4", 10.0, 20.0)

        # Temp UUID directories should be cleaned up
        entries = list(cache_dir.iterdir())
        assert all(e.is_file() for e in entries)


class TestGetThumbnail:
    @pytest.mark.asyncio
    async def test_cache_hit(self, service, cache_dir):
        cache_dir.mkdir(parents=True)
        from app.services.video_service import sha256_hash

        thumb_path = cache_dir / f"{sha256_hash('video.mp4')}_{2.0}.jpg"
        thumb_path.write_bytes(b"jpeg")

        result = await service.get_thumbnail("video.mp4", 2.0)
        assert result == str(thumb_path)

    @pytest.mark.asyncio
    async def test_raises_on_ffmpeg_failure(self, service, cache_dir):
        cache_dir.mkdir(parents=True)

        async def failing_ffmpeg(*args, **kwargs):
            proc = MagicMock()
            proc.wait = AsyncMock()
            proc.returncode = 1
            return proc

        with patch("asyncio.create_subprocess_exec", side_effect=failing_ffmpeg):
            with pytest.raises(FileNotFoundError):
                await service.get_thumbnail("video.mp4", 2.0)
