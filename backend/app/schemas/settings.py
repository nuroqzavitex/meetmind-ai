from pydantic import BaseModel, Field


class DiscordSettingsOut(BaseModel):
    configured: bool
    webhook_hint: str | None = None
    digest_enabled: bool


class DiscordSettingsIn(BaseModel):
    # Omitted keeps the saved webhook; null or "" removes it.
    webhook_url: str | None = Field(default=None, max_length=300)
    digest_enabled: bool


class DigestOut(BaseModel):
    orgs: int
    sent: int
    failed: int
