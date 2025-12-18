from pydantic import BaseModel, Field, computed_field
from typing import Optional

from .episode import Episode
from .utils import OptionalObjectIdStr


class Quote(BaseModel):
    id: OptionalObjectIdStr = Field(default=None, alias="_id")
    episode_id: str = Field(alias="episode")
    episode: Optional[Episode] = Field(default=None, exclude=True)
    person: str
    text: str
    timestamp: float = Field(alias="timestamp")

    model_config = {"populate_by_name": True}


class QuoteResult(BaseModel):
    id: OptionalObjectIdStr = Field(default=None, alias="_id")
    episode_id: str = Field(alias="episode", exclude=True)
    episode_data: Optional[Episode] = Field(default=None, serialization_alias="episode")
    person: str
    text: str
    timestamp: float
    matching_score: Optional[float] = Field(default=None, alias="MatchingScore")
    stream: bool = False

    @computed_field
    @property
    def season(self) -> int:
        return int(self.episode_id[1:3])

    @computed_field
    @property
    def episode_number(self) -> str:
        return self.episode_id[4:]

    model_config = {"populate_by_name": True}
