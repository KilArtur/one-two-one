"""Smoke checks for the TASK-001 repository scaffold."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_required_directories_exist() -> None:
    assert (ROOT / "backend" / "app").is_dir()
    assert (ROOT / "frontend" / "src").is_dir()
    assert (ROOT / "infra").is_dir()
    assert (ROOT / "docs").is_dir()


def test_env_example_contains_required_keys() -> None:
    env_text = (ROOT / ".env.example").read_text(encoding="utf-8")
    for key in [
        "DATABASE_URL=",
        "OPENAI_API_KEY=",
        "OPENAI_BASE_URL=",
        "LLM_MODEL=",
        "LLM_FAST_MODEL=",
        "REDIS_URL=",
        "CELERY_BROKER_URL=",
        "CELERY_RESULT_BACKEND=",
        "S3_ENDPOINT_URL=",
        "AUDIO_API_KEY=",
        "ASR_MODEL=",
        "TTS_MODEL=",
    ]:
        assert key in env_text


def test_compose_declares_postgres_and_redis() -> None:
    compose_text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "postgres:" in compose_text
    assert "redis:" in compose_text
    assert "pg_isready" in compose_text
    assert '["CMD", "redis-cli", "ping"]' in compose_text
