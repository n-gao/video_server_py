# Video Server

FastAPI video server with quote search and video streaming.

## Requirements

- Python 3.12+
- MongoDB
- FFmpeg

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

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VS_DB_CONNECTION_STRING` | `mongodb://localhost:27017` | MongoDB connection string |
| `VS_DB_DATABASE_NAME` | `sponge_db` | Database name |
| `VS_DB_QUOTE_COLLECTION_NAME` | `quotes` | Quotes collection |
| `VS_DB_EPISODE_COLLECTION_NAME` | `episodes` | Episodes collection |
| `VS_CACHE_FOLDER` | `.cache` | Cache directory |
| `VS_CACHE_SIZE` | `1000` | Max cached files |
| `VS_VIDEO_FOLDER` | `./videos` | Video files directory |
| `VS_VIDEO_FORMAT` | `.mp4` | Video file format |

## API Endpoints

- `GET /api/search?query=<text>&numResults=<n>` - Search quotes
- `GET /api/video/{season}/{episode}?start=<s>&duration=<d>` - Stream video segment
- `GET /api/thumbnail/{season}/{episode}?timestamp=<t>` - Get thumbnail
