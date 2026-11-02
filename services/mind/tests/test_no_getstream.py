"""Hard Rule 1: no GetStream / Vision-Agents dependency anywhere in Sense Mind."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = re.compile(r"^\s*(from|import)\s+(getstream|vision_agents)\b", re.M)


def test_no_forbidden_imports():
    offenders = [
        str(p.relative_to(ROOT))
        for p in (ROOT / "sense_mind").rglob("*.py")
        if FORBIDDEN.search(p.read_text(encoding="utf-8"))
    ]
    assert offenders == []


def test_pyproject_has_no_getstream():
    text = (ROOT / "pyproject.toml").read_text().lower()
    assert "getstream" not in text and "vision-agents" not in text
