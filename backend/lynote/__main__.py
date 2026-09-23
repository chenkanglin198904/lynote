import uvicorn

from lynote.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "lynote.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.should_reload(),
    )
