import asyncio
import hashlib
import platform
import shutil
import uuid
from pathlib import Path

from ..config import CacheSettings


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

    async def _get_segment(
        self, file_path: str, start: float, duration: float, tolerance: float = 10
    ) -> str:
        self._check_cache_size()

        # Generate cache file path
        cache_filename = f"{sha256_hash(file_path)}_{start}_{duration}.mp4".replace(
            ",", "-"
        )
        cache_file = Path(self.settings.folder) / cache_filename

        if cache_file.exists():
            return str(cache_file)

        # Create temporary folder for processing
        cache_folder = Path(self.settings.folder) / str(uuid.uuid4())
        cache_folder.mkdir(parents=True, exist_ok=True)

        try:
            # Format start and duration for FFmpeg
            start_s = f"{start - tolerance:.2f}"
            duration_s = f"{duration:.2f}"

            # First pass: segment the video
            segment_path = cache_folder / "seg%d.mp4"
            args = [
                self._ffmpeg,
                "-v",
                "quiet",
                "-i",
                file_path,
                "-c",
                "copy",
                "-ss",
                start_s,
                "-t",
                duration_s,
                "-f",
                "segment",
                "-y",
                str(segment_path),
            ]

            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await process.wait()

            # Get segment files and create concat list (skip first segment)
            segment_files = sorted(cache_folder.glob("seg*.mp4"))
            list_file = cache_folder / "list.txt"

            with open(list_file, "w") as f:
                for seg in segment_files[1:]:
                    f.write(f"file '{seg.absolute()}'\n")

            # Second pass: concatenate segments
            args = [
                self._ffmpeg,
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_file),
                "-c",
                "copy",
                str(cache_file),
            ]

            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await process.wait()

        finally:
            # Clean up temporary folder
            shutil.rmtree(cache_folder, ignore_errors=True)

        return str(cache_file)

    async def read_to_stream(
        self, file_path: str, start: float, duration: float
    ) -> str:
        """Returns path to the cached segment file."""
        cache_file = await self._get_segment(file_path, start, duration)
        return cache_file

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
