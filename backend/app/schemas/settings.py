from pydantic import BaseModel, Field


class DiscordSettingsOut(BaseModel):
    configured: bool
    webhook_hint: str | None = None
    digest_enabled: bool
    invite_url: str | None = None


class DiscordSettingsIn(BaseModel):
    # Omitted keeps the saved webhook; null or "" removes it.
    webhook_url: str | None = Field(default=None, max_length=300)
    digest_enabled: bool
    # Same convention: omitted keeps the saved link; null or "" removes it.
    invite_url: str | None = Field(default=None, max_length=200)


class DiscordBotOut(BaseModel):
    available: bool  # the backend has DISCORD_APP_ID and DISCORD_PUBLIC_KEY
    linked: bool
    link_code: str
    install_url: str | None = None


class DigestOut(BaseModel):
    orgs: int
    sent: int
    failed: int
