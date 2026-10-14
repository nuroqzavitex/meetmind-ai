import pytest

from app.core.config import Settings, normalize_database_url


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # Neon / Supabase style: plain scheme, libpq ssl params
        (
            "postgresql://u:p@ep-x.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require",
            "postgresql+asyncpg://u:p@ep-x.ap-southeast-1.aws.neon.tech/neondb?ssl=require",
        ),
        ("postgres://u:p@h:5432/db", "postgresql+asyncpg://u:p@h:5432/db"),
        ("postgresql://u:p@h/db?sslmode=verify-full", "postgresql+asyncpg://u:p@h/db?ssl=verify-full"),
        # already asyncpg: untouched
        ("postgresql+asyncpg://app:app@db:5432/meeting", "postgresql+asyncpg://app:app@db:5432/meeting"),
        ("postgresql+asyncpg://u:p@h/db?ssl=require", "postgresql+asyncpg://u:p@h/db?ssl=require"),
    ],
)
def test_normalize_database_url(raw: str, expected: str) -> None:
    assert normalize_database_url(raw) == expected


def test_settings_normalizes_database_url() -> None:
    s = Settings(_env_file=None, database_url="postgresql://u:p@h/db?sslmode=require")
    assert s.database_url == "postgresql+asyncpg://u:p@h/db?ssl=require"


def test_worker_poll_delay_defaults_to_arq_default_and_is_configurable() -> None:
    assert Settings(_env_file=None).worker_poll_delay == 0.5
    assert Settings(_env_file=None, worker_poll_delay=10).worker_poll_delay == 10


def test_worker_settings_use_configured_poll_delay() -> None:
    from app.core.config import get_settings
    from app.workers.main import WorkerSettings

    assert WorkerSettings.poll_delay == get_settings().worker_poll_delay
