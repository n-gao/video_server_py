from pydantic import BaseModel, Field

from .utils import ObjectIdStr


class Episode(BaseModel):
    id: ObjectIdStr = Field(alias="_id")
    title: str
    season: int
    episode_number: str = Field(alias="episode")

    model_config = {"populate_by_name": True}
