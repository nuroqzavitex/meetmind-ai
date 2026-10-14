import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class JoinCodeOut(BaseModel):
    code: str


class JoinRequestIn(BaseModel):
    code: str = Field(min_length=1, max_length=40)


class JoinRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    org_id: str
    org_name: str
    user_name: str
    user_email: str | None = None
    status: Literal["pending", "approved", "rejected", "cancelled"]
    created_at: dt.datetime
    decided_at: dt.datetime | None = None
    # Filled for approved requests when the org shared a Discord invite link.
    discord_invite_url: str | None = None
