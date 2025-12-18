from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware

from .config import settings
from .routers import video_router, quote_router
from .routers.quote import close_db_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown: close database connection
    await close_db_service()


app = FastAPI(
    title="Video Server",
    description="API for video streaming and quote search",
    version="1.0.0",
    lifespan=lifespan,
)

# Add response compression middleware (equivalent to ASP.NET's UseResponseCompression)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Include routers
app.include_router(video_router)
app.include_router(quote_router)


def main():
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.server.host,
        port=settings.server.port,
        reload=True,
    )


if __name__ == "__main__":
    main()
