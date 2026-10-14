from fastapi import APIRouter

from app.api.v1.endpoints import health, internal, items, jobs, meetings, qa, settings

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(meetings.router)
api_router.include_router(items.router)
api_router.include_router(jobs.router)
api_router.include_router(qa.router)
api_router.include_router(settings.router)
api_router.include_router(internal.router)
