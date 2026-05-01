from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from loguru import logger
import sys
import os
import mimetypes

mimetypes.add_type('audio/wav', '.wav')

from app.config import settings
from app.api.v1 import tts, asr, voice_models, users, auth, chat
from app.api.v1 import podcast, singing, digital_human, comic, comic_agent, workflow
from app.db.session import engine
from app.db.base import Base
import app.models


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application startup")
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # 种子数据初始化
    from app.db.session import AsyncSessionLocal
    from app.api.v1.comic_agent import seed_agent_data
    async with AsyncSessionLocal() as db:
        try:
            await seed_agent_data(db)
        except Exception as e:
            logger.warning(f"Seed data init skipped: {e}")
    
    yield
    
    logger.info("Application shutdown")
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="TTS/ASR Application with RAG, KG, and Agent capabilities",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level=settings.LOG_LEVEL,
)
logger.add(
    settings.LOG_FILE,
    rotation="500 MB",
    retention="10 days",
    level=settings.LOG_LEVEL,
)


@app.get("/")
async def root():
    return {
        "message": "Welcome to TTS Application API",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

app.include_router(auth.router, prefix=f"{settings.API_V1_PREFIX}/auth", tags=["Authentication"])
app.include_router(users.router, prefix=f"{settings.API_V1_PREFIX}/users", tags=["Users"])
app.include_router(tts.router, prefix=f"{settings.API_V1_PREFIX}/tts", tags=["TTS"])
app.include_router(asr.router, prefix=f"{settings.API_V1_PREFIX}/asr", tags=["ASR"])
app.include_router(voice_models.router, prefix=f"{settings.API_V1_PREFIX}/voice-models", tags=["Voice Models"])
app.include_router(chat.router, prefix=f"{settings.API_V1_PREFIX}/chat", tags=["Chat"])
app.include_router(podcast.router, prefix=f"{settings.API_V1_PREFIX}/podcast", tags=["Podcast"])
app.include_router(singing.router, prefix=f"{settings.API_V1_PREFIX}/singing", tags=["Singing"])
app.include_router(digital_human.router, prefix=f"{settings.API_V1_PREFIX}/digital-human", tags=["Digital Human"])
app.include_router(comic.router, prefix=f"{settings.API_V1_PREFIX}/comic", tags=["Comic"])
app.include_router(comic_agent.router, prefix=f"{settings.API_V1_PREFIX}/comic-agent", tags=["Comic Agent"])
app.include_router(workflow.router, prefix=f"{settings.API_V1_PREFIX}/workflows", tags=["Workflows"])


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Global exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
