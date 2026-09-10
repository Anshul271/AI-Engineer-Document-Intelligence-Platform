import traceback

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.config import settings
from app.database import init_db
from app.logging_config import get_logger

logger = get_logger(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    description="Intelligent Document Extraction, Validation & API Platform",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()
    logger.info("Database initialised. %s starting up.", settings.APP_NAME)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Fail gracefully: log the full traceback server-side, never leak it to the client."""
    logger.error("Unhandled exception on %s %s\n%s", request.method, request.url, traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"status": "FAILED", "error": "Internal server error. Please try again."},
    )


app.include_router(router, prefix="/api")

# Serve the static frontend at /
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
