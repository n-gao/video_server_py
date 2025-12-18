from fastapi import APIRouter, Depends, Query
from typing import List, Optional

from ..config import settings
from ..models import QuoteResult
from ..services import DbService

router = APIRouter(prefix="/api", tags=["quote"])


# Singleton instance of DbService
_db_service: Optional[DbService] = None


def get_db_service() -> DbService:
    global _db_service
    if _db_service is None:
        _db_service = DbService(settings.database)
    return _db_service


async def close_db_service() -> None:
    global _db_service
    if _db_service is not None:
        await _db_service.close()
        _db_service = None


@router.get("/search", response_model=List[QuoteResult])
async def get_search_results(
    query: str = Query(...),
    num_results: int = Query(default=10, alias="numResults"),
    db_service: DbService = Depends(get_db_service),
) -> List[QuoteResult]:
    """Search for quotes matching the given query.

    Args:
        query: Search query string
        num_results: Maximum number of results to return (1-20, default: 10)

    Returns:
        List of matching quotes with episode information
    """
    # Clamp numResults to valid range (1-20)
    num_results = max(1, min(20, num_results))
    return await db_service.search_quotes(query, num_results)
