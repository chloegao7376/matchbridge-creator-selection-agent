from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.briefs import router as briefs_router
from app.api.fit import router as fit_router
from app.api.health import router as health_router
from app.api.history_availability import router as history_availability_router
from app.api.recommendations import router as recommendations_router
from app.api.retrieval import router as retrieval_router
from app.api.selection_reviews import router as selection_reviews_router
from app.core.config import get_settings

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health_router)
app.include_router(briefs_router)
app.include_router(retrieval_router)
app.include_router(history_availability_router)
app.include_router(fit_router)
app.include_router(recommendations_router)
app.include_router(selection_reviews_router)
