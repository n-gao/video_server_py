from pydantic_settings import BaseSettings
from pydantic import Field

ENV_PREFIX = "VS_"


class DatabaseSettings(BaseSettings):
    episode_collection_name: str = Field(default="episodes")
    quote_collection_name: str = Field(default="quotes")
    connection_string: str = Field(default="mongodb://localhost:27017")
    database_name: str = Field(default="sponge_db")

    model_config = {
        "env_prefix": f"{ENV_PREFIX}DB_",
        "extra": "ignore",
    }


class CacheSettings(BaseSettings):
    folder: str = Field(default=".cache")
    size: int = Field(default=1000)

    model_config = {
        "env_prefix": f"{ENV_PREFIX}CACHE_",
        "extra": "ignore",
    }


class VideoSettings(BaseSettings):
    folder: str = Field(default="./videos")
    format: str = Field(default=".mp4")

    model_config = {
        "env_prefix": f"{ENV_PREFIX}VIDEO_",
        "extra": "ignore",
    }


class Settings(BaseSettings):
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    video: VideoSettings = Field(default_factory=VideoSettings)

    model_config = {
        "extra": "ignore",
    }


settings = Settings()
