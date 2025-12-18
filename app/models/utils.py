from pydantic import BeforeValidator
from typing import Annotated, Optional


def convert_objectid(v):
    """Convert MongoDB ObjectId to string."""
    if v is not None and not isinstance(v, str):
        return str(v)
    return v


ObjectIdStr = Annotated[str, BeforeValidator(convert_objectid)]
OptionalObjectIdStr = Annotated[Optional[str], BeforeValidator(convert_objectid)]
