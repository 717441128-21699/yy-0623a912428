from fastapi import APIRouter
from app.api.leads import router as leads_router
from app.api.stats import router as stats_router
from app.api.config import router as config_router

api_router = APIRouter()

api_router.include_router(leads_router)
api_router.include_router(stats_router)
api_router.include_router(config_router)
