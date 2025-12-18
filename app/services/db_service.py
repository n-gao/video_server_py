from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from typing import List
from ..config import DatabaseSettings
from ..models import Episode, QuoteResult


class DbService:
    def __init__(self, settings: DatabaseSettings):
        self.client = AsyncIOMotorClient(settings.connection_string)
        self.db: AsyncIOMotorDatabase = self.client[settings.database_name]
        self.quotes = self.db[settings.quote_collection_name]
        self.episodes = self.db[settings.episode_collection_name]

    async def search_quotes(self, query: str, num_results: int) -> List[QuoteResult]:
        # Build text search filter with German language
        text_filter = {"$text": {"$search": query, "$language": "german"}}

        # Project with text score
        projection = {"MatchingScore": {"$meta": "textScore"}}

        # Execute query with text score sorting
        cursor = (
            self.quotes.find(text_filter, projection)
            .sort([("MatchingScore", {"$meta": "textScore"})])
            .limit(num_results)
        )

        results = await cursor.to_list(length=num_results)

        # Get episode IDs from results
        episode_ids = [r["episode"] for r in results]

        # Fetch related episodes
        episodes_cursor = self.episodes.find({"_id": {"$in": episode_ids}})
        episodes_list = await episodes_cursor.to_list(length=len(episode_ids))
        episodes_dict = {ep["_id"]: Episode.model_validate(ep) for ep in episodes_list}

        # Build QuoteResult objects with joined episode data
        quote_results = []
        for r in results:
            quote_result = QuoteResult.model_validate(r)
            quote_result.episode_data = episodes_dict.get(r["episode"])
            quote_results.append(quote_result)

        return quote_results

    async def close(self):
        self.client.close()
