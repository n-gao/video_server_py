import asyncio
import hashlib
import platform
from pathlib import Path

from ..config import CacheSettings

# Tolerance for floating-point comparisons against keyframe timestamps (seconds).
_EPS = 1e-3


def sha256_hash(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


class VideoService:
    def __init__(self, settings: CacheSettings):
        self.settings = settings
        self._ffmpeg = "ffmpeg.exe" if platform.system() == "Windows" else "ffmpeg"
        self._ffprobe = "ffprobe.exe" if platform.system() == "Windows" else "ffprobe"

    def _check_cache_size(self) -> None:
        cache_folder = Path(self.settings.folder)
        if not cache_folder.exists():
            cache_folder.mkdir(parents=True, exist_ok=True)
            return

        files = list(cache_folder.glob("*"))
        if len(files) > self.settings.size:
            # Sort by last access time and delete oldest
            files_with_time = [(f, f.stat().st_atime) for f in files if f.is_file()]
            files_with_time.sort(key=lambda x: x[1])

            num_to_delete = len(files_with_time) - self.settings.size
            for f, _ in files_with_time[:num_to_delete]:
                try:
                    f.unlink()
                except OSError:
                    pass

    async def _run_ffprobe(self, args: list[str]) -> str:
        process = await asyncio.create_subprocess_exec(
            self._ffprobe,
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await process.communicate()
        return stdout.decode()

    async def _probe_duration(self, path: str) -> float:
        out = (
            await self._run_ffprobe(
                ["-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", path]
            )
        ).strip()
        try:
            return float(out)
        except ValueError:
            return 0.0

    async def _probe_keyframes(self, file_path: str) -> list[float]:
        """Return sorted video keyframe timestamps (seconds) from packet flags."""
        out = await self._run_ffprobe(
            [
                "-v",
                "quiet",
                "-select_streams",
                "v:0",
                "-show_entries",
                "packet=pts_time,flags",
                "-of",
                "csv=p=0",
                file_path,
            ]
        )
        times: list[float] = []
        for line in out.splitlines():
            parts = line.split(",")
            if len(parts) >= 2 and "K" in parts[1]:
                try:
                    times.append(float(parts[0]))
                except ValueError:
                    pass
        return sorted(times)

    async def _keyframe_bounds(
        self, file_path: str, start: float, duration: float
    ) -> tuple[float, float]:
        """Snap [start, start+duration] outward to enclosing keyframe boundaries.

        Returns ``(actual_start, copy_end)`` in source-relative seconds. The
        start is the latest keyframe at or before ``start`` (so the requested
        moment is included); the end is the earliest keyframe at or after the
        requested end, or the source duration if none is later.
        """
        keyframes = await self._probe_keyframes(file_path)
        source_duration = await self._probe_duration(file_path)

        before = [k for k in keyframes if k <= start + _EPS]
        actual_start = before[-1] if before else (keyframes[0] if keyframes else 0.0)

        desired_end = start + duration
        after = [k for k in keyframes if k >= desired_end - _EPS]
        copy_end = after[0] if after else source_duration

        return actual_start, max(copy_end, actual_start)

    async def _get_segment(
        self,
        file_path: str,
        start: float,
        duration: float,
        exact: bool = False,
    ) -> tuple[str, float, float]:
        """Produce (and cache) a segment.

        Returns ``(cache_path, actual_start, actual_duration)`` where the actual
        values reflect what the produced clip really covers — identical to the
        request when ``exact`` is True, snapped to keyframes otherwise.
        """
        self._check_cache_size()

        suffix = "_exact" if exact else ""
        cache_filename = (
            f"{sha256_hash(file_path)}_{start}_{duration}{suffix}.mp4".replace(",", "-")
        )
        cache_file = Path(self.settings.folder) / cache_filename

        if exact:
            if not cache_file.exists():
                await self._transcode_segment(file_path, start, duration, cache_file)
            actual_duration = await self._probe_duration(str(cache_file))
            return str(cache_file), start, actual_duration

        actual_start, copy_end = await self._keyframe_bounds(file_path, start, duration)

        if not cache_file.exists():
            await self._copy_segment(
                file_path, actual_start, copy_end - actual_start, cache_file
            )

        actual_duration = await self._probe_duration(str(cache_file))
        return str(cache_file), actual_start, actual_duration

    async def _copy_segment(
        self, file_path: str, start: float, duration: float, cache_file: Path
    ) -> None:
        """Stream-copy a segment starting at a keyframe (no re-encode)."""
        args = [
            self._ffmpeg,
            "-v",
            "quiet",
            "-ss",
            f"{start:.3f}",
            "-i",
            file_path,
            "-t",
            f"{duration:.3f}",
            "-c",
            "copy",
            "-y",
            str(cache_file),
        ]

        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await process.wait()
        if process.returncode != 0:
            raise FileNotFoundError(f"Could not extract segment for {file_path}")

    async def _transcode_segment(
        self, file_path: str, start: float, duration: float, cache_file: Path
    ) -> None:
        """Re-encode a frame-accurate segment instead of copying at keyframes."""
        args = [
            self._ffmpeg,
            "-v",
            "quiet",
            "-ss",
            f"{start:.2f}",
            "-i",
            file_path,
            "-t",
            f"{duration:.2f}",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-y",
            str(cache_file),
        ]

        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await process.wait()
        if process.returncode != 0:
            raise FileNotFoundError(f"Could not transcode segment for {file_path}")

    async def read_to_stream(
        self, file_path: str, start: float, duration: float, exact: bool = False
    ) -> tuple[str, float, float]:
        """Return ``(cache_path, actual_start, actual_duration)`` for a segment.

        When ``exact`` is True the segment is re-encoded for frame-accurate
        trimming and the actual bounds match the request. Otherwise it is
        stream-copied at the enclosing keyframes, and the returned actual
        start/duration tell the caller what the clip really covers.
        """
        return await self._get_segment(file_path, start, duration, exact=exact)

    async def get_thumbnail(self, file_path: str, timestamp: float) -> str:
        """Returns path to the cached thumbnail file."""
        self._check_cache_size()

        cache_filename = f"{sha256_hash(file_path)}_{timestamp}.jpg"
        cache_path = Path(self.settings.folder) / cache_filename

        if not cache_path.exists():
            start_s = f"{timestamp:.2f}"

            args = [
                self._ffmpeg,
                "-ss",
                start_s,
                "-i",
                file_path,
                "-an",
                "-vframes",
                "1",
                "-f",
                "image2pipe",
                "-y",
                str(cache_path),
            ]

            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await process.wait()
            if process.returncode != 0:
                raise FileNotFoundError(f"Could not create thumbnail for {file_path}")
        return str(cache_path)
