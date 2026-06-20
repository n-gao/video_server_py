from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from pathlib import Path
from ..config import settings
from ..services import VideoService


router = APIRouter(prefix="/api", tags=["video"])


def get_video_service() -> VideoService:
    return VideoService(settings.cache)


def get_file_path(season: int, episode: str) -> str:
    """Convert season and episode to file path.

    Handles both single episodes (e.g., "5") and multi-part episodes (e.g., "5a").
    """
    video_settings = settings.video
    episode_minor = episode[-1]

    if episode_minor.isalpha():
        episode_major = int(episode[:-1])
        filename = (
            f"s{season:02d}e{episode_major:02d}{episode_minor}{video_settings.format}"
        )
    else:
        episode_major = int(episode)
        filename = f"s{season:02d}e{episode_major:02d}{video_settings.format}"

    return str(Path(video_settings.folder) / f"s{season:02d}" / filename)


@router.get("/video/{season}/{episode}")
async def get_video(
    season: int,
    episode: str,
    start: float,
    duration: float = Query(default=20),
    exact: bool = Query(default=False),
    video_service: VideoService = Depends(get_video_service),
):
    """Get a video segment for the specified season and episode.

    Args:
        season: Season number
        episode: Episode identifier (e.g., "1", "1a")
        start: Start time in seconds (default: 0)
        duration: Duration in seconds (default: 20)
        exact: Trim at exact frames via transcoding instead of snipping at the
            closest keyframes (default: False)

    Returns:
        Video file stream (video/mp4). The actual start and duration of the
        returned clip are reported in the ``X-Actual-Start`` and
        ``X-Actual-Duration`` response headers — for ``exact=False`` these are
        snapped to keyframes and so may differ from the requested values.
    """
    file_path = get_file_path(season, episode)
    cache_file, actual_start, actual_duration = await video_service.read_to_stream(
        file_path, start, duration, exact=exact
    )
    return FileResponse(
        cache_file,
        media_type="video/mp4",
        headers={
            "X-Actual-Start": f"{actual_start:.3f}",
            "X-Actual-Duration": f"{actual_duration:.3f}",
            # Allow browser JS (fetch) to read the custom headers cross-origin.
            "Access-Control-Expose-Headers": "X-Actual-Start, X-Actual-Duration",
        },
    )


@router.get("/thumbnail/{season}/{episode}")
async def get_thumbnail(
    season: int,
    episode: str,
    timestamp: float,
    video_service: VideoService = Depends(get_video_service),
):
    """Get a thumbnail image for the specified season and episode.

    Args:
        season: Season number
        episode: Episode identifier (e.g., "1", "1a")
        timestamp: Timestamp in seconds to capture (default: 2)

    Returns:
        JPEG image file stream (image/jpeg)
    """
    file_path = get_file_path(season, episode)
    cache_file = await video_service.get_thumbnail(file_path, timestamp)
    return FileResponse(cache_file, media_type="image/jpeg")
