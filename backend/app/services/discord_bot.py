"""Discord /hoi bot: link a Discord server to an org, answer questions with the Q&A service."""

import logging
import re
import secrets
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.config import AISettings
from app.ai.llm import LLMClient
from app.ai.retrieval.embedder import Embedder
from app.core.auth import Principal, require_admin
from app.core.config import Settings
from app.core.errors import AppError
from app.models import OrgSettings
from app.notify.discord import DiscordClient, DiscordError
from app.notify.discord_bot import (
    ASK_COMMAND,
    DEFERRED_CHANNEL_MESSAGE,
    LINK_COMMAND,
    answer_message,
    can_manage_server,
    ephemeral,
    error_message,
    option,
)
from app.repositories import org_settings as settings_repo
from app.schemas.settings import DiscordBotOut
from app.services import qa
from app.services.join_requests import ALPHABET

logger = logging.getLogger(__name__)

MAX_QUESTION = 500


def new_link_code() -> str:
    body = "".join(secrets.choice(ALPHABET) for _ in range(8))
    return f"DC-{body[:4]}-{body[4:]}"


def normalize_link_code(raw: str) -> str | None:
    s = re.sub(r"[^A-Z0-9]", "", raw.upper())
    if len(s) == 10 and s.startswith("DC"):
        s = s[2:]
    if len(s) != 8 or any(c not in ALPHABET for c in s):
        return None
    return f"DC-{s[:4]}-{s[4:]}"


def _available(settings: Settings) -> bool:
    return bool(settings.discord_app_id and settings.discord_public_key)


def install_url(app_id: str) -> str:
    return f"https://discord.com/oauth2/authorize?client_id={app_id}&scope=applications.commands"


async def _unused_code(session: AsyncSession) -> str:
    while True:
        code = new_link_code()
        taken = await session.scalar(
            select(OrgSettings.org_id).where(OrgSettings.discord_link_code == code)
        )
        if taken is None:
            return code


def _out(row: OrgSettings, settings: Settings) -> DiscordBotOut:
    return DiscordBotOut(
        available=_available(settings),
        linked=row.discord_guild_id is not None,
        link_code=row.discord_link_code or "",
        install_url=install_url(settings.discord_app_id) if settings.discord_app_id else None,
    )


async def get_bot(session: AsyncSession, settings: Settings, *, principal: Principal) -> DiscordBotOut:
    require_admin(principal)
    row = await settings_repo.get_or_create(session, org_id=principal.org_id)
    if row.discord_link_code is None:
        row.discord_link_code = await _unused_code(session)
        await session.commit()
    return _out(row, settings)


async def rotate_code(
    session: AsyncSession, settings: Settings, *, principal: Principal
) -> DiscordBotOut:
    require_admin(principal)
    row = await settings_repo.get_or_create(session, org_id=principal.org_id)
    row.discord_link_code = await _unused_code(session)
    await session.commit()
    return _out(row, settings)


async def unlink(session: AsyncSession, settings: Settings, *, principal: Principal) -> DiscordBotOut:
    require_admin(principal)
    row = await settings_repo.get_or_create(session, org_id=principal.org_id)
    row.discord_guild_id = None
    await session.commit()
    return _out(row, settings)


# --- interactions ---


async def _link(session: AsyncSession, payload: dict[str, Any], guild_id: str) -> dict[str, Any]:
    member = payload.get("member") or {}
    if not can_manage_server(member.get("permissions")):
        return ephemeral("Chỉ người có quyền quản lý server (Manage Server) mới liên kết được.")
    code = normalize_link_code(option(payload.get("data") or {}, "ma"))
    row = None
    if code:
        row = await session.scalar(select(OrgSettings).where(OrgSettings.discord_link_code == code))
    if row is None:
        return ephemeral("Mã liên kết không đúng. Admin MeetMind lấy mã ở trang Cài đặt → Bot hỏi đáp.")
    previous = await session.scalar(
        select(OrgSettings).where(OrgSettings.discord_guild_id == guild_id)
    )
    if previous is not None and previous is not row:
        previous.discord_guild_id = None  # one server answers for one org
        await session.flush()
    row.discord_guild_id = guild_id
    await session.commit()
    return ephemeral(
        "✅ Đã liên kết server này với tổ chức trên MeetMind. Mọi người dùng `/hoi <câu hỏi>` "
        "để hỏi về các cuộc họp đã phát hành."
    )


async def handle_command(
    session: AsyncSession, payload: dict[str, Any]
) -> tuple[dict[str, Any], str | None, str]:
    """Immediate response, plus (org_id, question) when an answer must follow in the background."""
    data = payload.get("data") or {}
    name = data.get("name")
    guild_id = payload.get("guild_id")
    if not guild_id:
        return ephemeral("Hãy dùng lệnh này trong server Discord đã liên kết với MeetMind."), None, ""
    if name == LINK_COMMAND:
        return await _link(session, payload, str(guild_id)), None, ""
    if name != ASK_COMMAND:
        return ephemeral("Lệnh không được hỗ trợ."), None, ""
    row = await session.scalar(
        select(OrgSettings).where(OrgSettings.discord_guild_id == str(guild_id))
    )
    if row is None:
        return (
            ephemeral(
                "Server này chưa liên kết với tổ chức nào trên MeetMind. Admin gõ `/ketnoi <mã>` "
                "(mã ở trang Cài đặt → Bot hỏi đáp)."
            ),
            None,
            "",
        )
    question = option(data, "cau_hoi")[:MAX_QUESTION]
    if not question:
        return ephemeral("Hãy nhập câu hỏi, ví dụ: `/hoi Chốt dùng CSDL nào?`"), None, ""
    return {"type": DEFERRED_CHANNEL_MESSAGE}, row.org_id, question


async def answer_in_background(
    sm: async_sessionmaker[AsyncSession],
    discord: DiscordClient,
    llm: LLMClient,
    embedder: Embedder,
    ai: AISettings,
    *,
    org_id: str,
    payload: dict[str, Any],
    question: str,
    app_url: str,
) -> None:
    app_id, token = str(payload.get("application_id", "")), str(payload.get("token", ""))
    user = ((payload.get("member") or {}).get("user") or {})
    principal = Principal(
        user_id=f"discord:{user.get('id', '?')}", org_id=org_id,
        name=str(user.get("global_name") or user.get("username") or "Discord"),
    )
    try:
        async with sm() as session:
            result = await qa.ask(
                session, llm, embedder, ai,
                principal=principal, question=question, project=None, today=date.today(),
            )
        message = answer_message(question, result, app_url)
    except AppError as exc:
        message = error_message(exc.message)
    except Exception:
        logger.exception("Discord /hoi failed for org %s", org_id)
        message = error_message("Có lỗi khi trả lời, vui lòng thử lại sau.")
    try:
        await discord.edit_original(app_id, token, message)
    except DiscordError:
        logger.exception("Could not deliver the Discord answer for org %s", org_id)
