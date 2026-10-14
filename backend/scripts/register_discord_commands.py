"""Register the /hoi and /ketnoi slash commands for the Discord application (run once).

Needs DISCORD_APP_ID and DISCORD_BOT_TOKEN in the environment or the repo-root .env:

    cd backend && uv run python scripts/register_discord_commands.py
"""

import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings  # noqa: E402
from app.notify.discord_bot import ASK_COMMAND, LINK_COMMAND, MANAGE_GUILD  # noqa: E402

STRING = 3
GUILD_INSTALL = 0
GUILD_CONTEXT = 0

COMMANDS = [
    {
        "name": ASK_COMMAND,
        "description": "Hỏi về các cuộc họp đã phát hành trên MeetMind",
        "options": [{
            "type": STRING, "name": "cau_hoi", "description": "Câu hỏi của bạn",
            "required": True, "max_length": 500,
        }],
        "integration_types": [GUILD_INSTALL],
        "contexts": [GUILD_CONTEXT],
    },
    {
        "name": LINK_COMMAND,
        "description": "Liên kết server này với một tổ chức trên MeetMind (cần quyền quản lý server)",
        "options": [{
            "type": STRING, "name": "ma", "description": "Mã liên kết DC-XXXX-XXXX ở trang Cài đặt",
            "required": True, "max_length": 20,
        }],
        "default_member_permissions": str(MANAGE_GUILD),
        "integration_types": [GUILD_INSTALL],
        "contexts": [GUILD_CONTEXT],
    },
]


def main() -> int:
    s = get_settings()
    if not s.discord_app_id or s.discord_bot_token is None:
        print("Set DISCORD_APP_ID and DISCORD_BOT_TOKEN first.", file=sys.stderr)
        return 2
    r = httpx.put(
        f"https://discord.com/api/v10/applications/{s.discord_app_id}/commands",
        headers={"Authorization": f"Bot {s.discord_bot_token.get_secret_value()}"},
        json=COMMANDS,
        timeout=20,
    )
    if r.status_code >= 300:
        print(f"Discord refused ({r.status_code}): {r.text}", file=sys.stderr)
        return 1
    print("Registered:", ", ".join("/" + c["name"] for c in r.json()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
