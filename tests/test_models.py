from app.models.utils import convert_objectid
from app.models import Episode, Quote, QuoteResult


class TestConvertObjectId:
    def test_none_passthrough(self):
        assert convert_objectid(None) is None

    def test_str_passthrough(self):
        assert convert_objectid("abc") == "abc"

    def test_int_converted(self):
        assert convert_objectid(123) == "123"

    def test_object_converted(self):
        class FakeObjectId:
            def __str__(self):
                return "fake_id"

        assert convert_objectid(FakeObjectId()) == "fake_id"


class TestEpisode:
    def test_from_alias(self):
        ep = Episode.model_validate({"_id": "s01e05", "title": "Test", "season": 1, "episode": "5"})
        assert ep.id == "s01e05"
        assert ep.title == "Test"
        assert ep.season == 1
        assert ep.episode == "5"

    def test_objectid_converted(self):
        ep = Episode.model_validate({"_id": 12345, "title": "T", "season": 1, "episode": "1"})
        assert ep.id == "12345"


class TestQuote:
    def test_from_field_name(self):
        q = Quote.model_validate({
            "episode_id": "s01e05",
            "person": "Bob",
            "text": "Hello",
            "timestamp": 10.5,
        })
        assert q.episode_id == "s01e05"
        assert q.person == "Bob"
        assert q.text == "Hello"
        assert q.timestamp == 10.5
        assert q.id is None

    def test_with_id(self):
        q = Quote.model_validate({
            "_id": "abc",
            "episode_id": "s01e01",
            "person": "A",
            "text": "B",
            "timestamp": 0,
        })
        assert q.id == "abc"


class TestQuoteResult:
    def _make(self, episode_id="s01e05", **kwargs):
        defaults = {"person": "Bob", "text": "Hello", "timestamp": 10.5}
        defaults.update(kwargs)
        return QuoteResult.model_validate({"episode": episode_id, **defaults})

    def test_season_computed(self):
        assert self._make("s01e05").season == 1
        assert self._make("s10e03").season == 10

    def test_episode_number_computed(self):
        assert self._make("s01e05").episode_number == "05"
        assert self._make("s10e03a").episode_number == "03a"

    def test_serialization_excludes_episode_id(self):
        qr = self._make("s01e05")
        data = qr.model_dump(by_alias=True)
        assert "episode_id" not in data
        # episode_data serialized as "episode"
        assert "episode" in data

    def test_serialization_includes_computed(self):
        qr = self._make("s05e12")
        data = qr.model_dump()
        assert data["season"] == 5
        assert data["episode_number"] == "12"

    def test_matching_score_alias(self):
        qr = QuoteResult.model_validate({
            "episode": "s01e01",
            "person": "A",
            "text": "B",
            "timestamp": 0,
            "MatchingScore": 1.5,
        })
        assert qr.matching_score == 1.5

    def test_with_episode_data(self):
        ep = Episode.model_validate({"_id": "s01e05", "title": "Test", "season": 1, "episode": "5"})
        qr = self._make("s01e05")
        qr.episode_data = ep
        data = qr.model_dump(by_alias=True)
        assert data["episode"]["title"] == "Test"
