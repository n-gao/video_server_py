import os
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


def fake_subprocess(
    *,
    keyframes=(0.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0),
    source_duration=30.0,
    output_duration=20.0,
    returncode=0,
    source_name="video.mp4",
):
    """Build a create_subprocess_exec stand-in for both ffprobe and ffmpeg.

    ffprobe calls answer via ``communicate()`` (keyframe packets or duration);
    ffmpeg calls answer via ``wait()`` and write the output file at args[-1].
    """

    async def fake(*args, **kwargs):
        prog = str(args[0])
        argstr = " ".join(str(a) for a in args)
        proc = MagicMock()
        proc.returncode = returncode

        if "ffprobe" in prog:
            if "packet=pts_time,flags" in argstr:
                data = "".join(f"{t:.6f},K__\n" for t in keyframes)
            else:  # format=duration — distinguish source from produced clip
                path = str(args[-1])
                dur = source_duration if path.endswith(source_name) else output_duration
                data = f"{dur:.6f}\n"
            proc.communicate = AsyncMock(return_value=(data.encode(), b""))
            return proc

        # ffmpeg: produce the output file unless we're simulating a failure
        proc.wait = AsyncMock()
        if returncode == 0:
            Path(args[-1]).write_bytes(b"clip")
        return proc

    return fake


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

        # Cache key uses the *requested* start/duration, not the snapped values
        expected_name = f"{sha256_hash('video.mp4')}_{12.0}_{20.0}.mp4"
        expected_path = cache_dir / expected_name
        expected_path.write_bytes(b"cached")

        # Even on a cache hit ffmpeg must not run, but ffprobe still reports the
        # actual keyframe-snapped bounds.
        fake = fake_subprocess(keyframes=(0.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0))
        with patch("asyncio.create_subprocess_exec", side_effect=fake):
            path, actual_start, actual_duration = await service._get_segment(
                "video.mp4", 12.0, 20.0
            )
        assert path == str(expected_path)
        # start snaps back to keyframe 10.0; duration reflects the produced file
        assert actual_start == 10.0
        assert actual_duration == 20.0
        assert expected_path.read_bytes() == b"cached"  # not regenerated

    @pytest.mark.asyncio
    async def test_snaps_to_keyframe_bounds(self, service, cache_dir):
        cache_dir.mkdir(parents=True)
        captured = {}

        fake = fake_subprocess(keyframes=(0.0, 8.0, 16.0, 24.0), source_duration=30.0)

        async def wrapped(*args, **kwargs):
            if "ffprobe" not in str(args[0]):
                captured["ffmpeg"] = args
            return await fake(*args, **kwargs)

        with patch("asyncio.create_subprocess_exec", side_effect=wrapped):
            # request [10, 23] -> snaps to keyframes [8, 24]
            path, actual_start, _ = await service._get_segment("video.mp4", 10.0, 13.0)

        assert Path(path).exists()
        assert actual_start == 8.0
        ff = captured["ffmpeg"]
        assert "copy" in ff  # stream copy, no re-encode
        assert "libx264" not in ff
        # ffmpeg seeks to the keyframe start and copies up to the next keyframe
        assert f"{8.0:.3f}" in ff
        assert f"{16.0:.3f}" in ff  # duration 24 - 8

    @pytest.mark.asyncio
    async def test_raises_on_ffmpeg_failure(self, service, cache_dir):
        cache_dir.mkdir(parents=True)
        fake = fake_subprocess(returncode=1)
        with patch("asyncio.create_subprocess_exec", side_effect=fake):
            with pytest.raises(FileNotFoundError):
                await service._get_segment("video.mp4", 10.0, 20.0)


class TestExactSegment:
    @pytest.mark.asyncio
    async def test_exact_cache_filename_has_suffix(self, service, cache_dir):
        cache_dir.mkdir(parents=True)
        from app.services.video_service import sha256_hash

        expected_name = f"{sha256_hash('video.mp4')}_{10.0}_{20.0}_exact.mp4"
        expected_path = cache_dir / expected_name
        expected_path.write_bytes(b"cached")

        fake = fake_subprocess(output_duration=20.0)
        with patch("asyncio.create_subprocess_exec", side_effect=fake):
            path, actual_start, actual_duration = await service._get_segment(
                "video.mp4", 10.0, 20.0, exact=True
            )
        assert path == str(expected_path)
        # exact bounds match the request
        assert actual_start == 10.0
        assert actual_duration == 20.0

    @pytest.mark.asyncio
    async def test_exact_transcodes_single_pass(self, service, cache_dir):
        cache_dir.mkdir(parents=True)
        captured = {}

        fake = fake_subprocess()

        async def wrapped(*args, **kwargs):
            if "ffprobe" not in str(args[0]):
                captured["ffmpeg"] = args
            return await fake(*args, **kwargs)

        with patch("asyncio.create_subprocess_exec", side_effect=wrapped):
            path, _, _ = await service.read_to_stream(
                "video.mp4", 10.0, 20.0, exact=True
            )

        assert Path(path).exists()
        assert path.endswith("_exact.mp4")
        # Re-encode, not stream copy
        assert "libx264" in captured["ffmpeg"]
        assert "aac" in captured["ffmpeg"]
        assert "copy" not in captured["ffmpeg"]
        assert all(e.is_file() for e in cache_dir.iterdir())

    @pytest.mark.asyncio
    async def test_exact_raises_on_ffmpeg_failure(self, service, cache_dir):
        cache_dir.mkdir(parents=True)
        fake = fake_subprocess(returncode=1)
        with patch("asyncio.create_subprocess_exec", side_effect=fake):
            with pytest.raises(FileNotFoundError):
                await service.read_to_stream("video.mp4", 10.0, 20.0, exact=True)


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
        fake = fake_subprocess(source_duration=30.0, returncode=1)
        with patch("asyncio.create_subprocess_exec", side_effect=fake):
            with pytest.raises(FileNotFoundError):
                await service.get_thumbnail("video.mp4", 2.0)

    @pytest.mark.asyncio
    async def test_clamps_negative_timestamp_to_start(self, service, cache_dir):
        cache_dir.mkdir(parents=True)
        captured = {}
        fake = fake_subprocess(source_duration=30.0)

        async def wrapped(*args, **kwargs):
            if "ffprobe" not in str(args[0]):
                captured["ffmpeg"] = args
            return await fake(*args, **kwargs)

        with patch("asyncio.create_subprocess_exec", side_effect=wrapped):
            result = await service.get_thumbnail("video.mp4", -5.0)

        assert Path(result).exists()
        # Captures at the start, and caches under the clamped value
        assert "0.00" in captured["ffmpeg"]
        assert result.endswith("_0.0.jpg")

    @pytest.mark.asyncio
    async def test_clamps_timestamp_past_end(self, service, cache_dir):
        cache_dir.mkdir(parents=True)
        captured = {}
        fake = fake_subprocess(source_duration=30.0)

        async def wrapped(*args, **kwargs):
            if "ffprobe" not in str(args[0]):
                captured["ffmpeg"] = args
            return await fake(*args, **kwargs)

        with patch("asyncio.create_subprocess_exec", side_effect=wrapped):
            result = await service.get_thumbnail("video.mp4", 45.0)

        assert Path(result).exists()
        # Clamped to just before the end (duration - margin = 29.9)
        assert "29.90" in captured["ffmpeg"]
        assert result.endswith("_29.9.jpg")

    @pytest.mark.asyncio
    async def test_unreadable_source_raises_not_found(self, service, cache_dir):
        cache_dir.mkdir(parents=True)
        # Probe returns no duration -> source can't be read.
        fake = fake_subprocess(source_duration=0.0)
        with patch("asyncio.create_subprocess_exec", side_effect=fake):
            with pytest.raises(FileNotFoundError):
                await service.get_thumbnail("video.mp4", 2.0)

    @pytest.mark.asyncio
    async def test_valid_timestamp_generates(self, service, cache_dir):
        cache_dir.mkdir(parents=True)
        fake = fake_subprocess(source_duration=30.0)
        with patch("asyncio.create_subprocess_exec", side_effect=fake):
            result = await service.get_thumbnail("video.mp4", 2.0)
        assert Path(result).exists()
        assert result.endswith(".jpg")
