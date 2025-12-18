from pydantic import BaseModel, Field

from .utils import ObjectIdStr


class Episode(BaseModel):
    id: ObjectIdStr = Field(alias="_id")
    title: str
    season: int
    episode: str

    model_config = {"populate_by_name": True}
