# Video Server

A FastAPI server for searching TV show quotes and streaming the corresponding video clips. Quotes are stored in MongoDB with full-text search (German language), and video segments are extracted on-the-fly using FFmpeg with an LRU disk cache.

## Requirements

- Python 3.12+
- MongoDB
- FFmpeg

## Database Schema

The server expects two MongoDB collections:

### `episodes`

Each document represents a single episode.

| Field     | Type     | Description                                              |
|-----------|----------|----------------------------------------------------------|
| `_id`     | `string` | Unique identifier, e.g. `s01e05` or `s02e03a`           |
| `title`   | `string` | Episode title                                            |
| `season`  | `int`    | Season number                                            |
| `episode` | `string` | Episode identifier within the season, e.g. `5` or `3a`  |

### `quotes`

Each document represents a single quote. The collection must have a [text index](https://www.mongodb.com/docs/manual/core/indexes/index-types/index-text/) on the `text` field with `default_language: "german"` for search to work.

| Field       | Type     | Description                                       |
|-------------|----------|---------------------------------------------------|
| `_id`       | ObjectId | Auto-generated                                    |
| `episode`   | `string` | References `episodes._id`, e.g. `s01e05`          |
| `person`    | `string` | Name of the speaker                               |
| `text`      | `string` | The quote text (indexed for full-text search)      |
| `timestamp` | `float`  | Timestamp in seconds where the quote occurs        |

#### Required Index

```javascript
db.quotes.createIndex(
  { text: "text" },
  { default_language: "german" }
)
```

## Video File Layout

Video files must be organized as:

```
<VS_VIDEO_FOLDER>/
  s01/
    s01e01.mp4
    s01e02.mp4
    s01e03a.mp4   # multi-part episode
    s01e03b.mp4
  s02/
    s02e01.mp4
    ...
```

## Setup

1. Copy `.env.example` to `.env` and configure:
```bash
cp .env.example .env
```

2. Install dependencies:
```bash
uv sync
```

3. Run the server:
```bash
uv run video-server
```

## Docker

```bash
docker compose up -d
```

Pre-built multiplatform images (amd64/arm64) are published to `ghcr.io` on every push to `main`.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VS_DB_CONNECTION_STRING` | `mongodb://localhost:27017` | MongoDB connection string |
| `VS_DB_DATABASE_NAME` | `video_server` | Database name |
| `VS_DB_QUOTE_COLLECTION_NAME` | `quotes` | Quotes collection name |
| `VS_DB_EPISODE_COLLECTION_NAME` | `episodes` | Episodes collection name |
| `VS_CACHE_FOLDER` | `.cache` | Cache directory for extracted clips/thumbnails |
| `VS_CACHE_SIZE` | `1000` | Max number of cached files (LRU eviction) |
| `VS_VIDEO_FOLDER` | `./videos` | Root directory for video files |
| `VS_VIDEO_FORMAT` | `.mp4` | Video file extension |

## API Endpoints

### Search Quotes

```
GET /api/search?query=<text>&numResults=<n>
```

Full-text search over quotes. Returns up to `numResults` (1-20, default 10) matches ranked by relevance, each including the linked episode data.

### Stream Video Segment

```
GET /api/video/{season}/{episode}?start=<seconds>&duration=<seconds>
```

Extracts and streams a video segment via FFmpeg. Default duration is 20 seconds. Results are cached on disk.

### Get Thumbnail

```
GET /api/thumbnail/{season}/{episode}?timestamp=<seconds>
```

Returns a JPEG thumbnail captured at the given timestamp (default 2 seconds).
