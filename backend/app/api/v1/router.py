from fastapi import APIRouter

from app.api.v1.endpoints import (
    discord,
    health,
    internal,
    items,
    jobs,
    join_requests,
    meetings,
    overview,
    qa,
    settings,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(meetings.router)
api_router.include_router(items.router)
api_router.include_router(jobs.router)
api_router.include_router(qa.router)
api_router.include_router(settings.router)
api_router.include_router(internal.router)
api_router.include_router(join_requests.router)
api_router.include_router(discord.router)
api_router.include_router(overview.router)
