"""Smoke tests for monorepo scaffold (TASK-001)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_scaffold_directories_exist() -> None:
    expected = [
        ROOT / "backend" / "app",
        ROOT / "frontend" / "src",
        ROOT / "infra",
        ROOT / "docs",
    ]
    missing = [str(path) for path in expected if not path.is_dir()]
    assert missing == [], f"Missing scaffold dirs: {missing}"


def test_docker_compose_and_env_example_exist() -> None:
    assert (ROOT / "docker-compose.yml").is_file()
    assert (ROOT / ".env.example").is_file()
