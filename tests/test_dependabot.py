"""Dependabot proposes a release only after it has been out for a week."""

from pathlib import Path

import pytest
import yaml

_CONFIG = Path(__file__).resolve().parents[1] / ".github" / "dependabot.yml"

pytestmark = pytest.mark.skipif(not _CONFIG.is_file(), reason=".github/dependabot.yml is not part of this source tree")

MINIMUM_COOLDOWN_DAYS = 7


def _updates() -> list[dict]:
    config = yaml.safe_load(_CONFIG.read_text(encoding="utf-8"))
    assert config["version"] == 2
    return config["updates"]


def test_every_ecosystem_waits_at_least_a_week_after_a_release() -> None:
    updates = _updates()

    assert updates
    for update in updates:
        cooldown = update.get("cooldown", {})
        days = [cooldown.get("default-days", 0)] + [cooldown[key] for key in cooldown if key.startswith("semver-")]
        assert min(days) >= MINIMUM_COOLDOWN_DAYS, (update["package-ecosystem"], cooldown)
        assert "include" not in cooldown and "exclude" not in cooldown, (update["package-ecosystem"], cooldown)
