"""The single source of truth for commands exposed by the bot and website."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CATALOG_PATH = Path("data/command_catalog.json")


def _clean(text: str | None, fallback: str) -> str:
    value = " ".join((text or "").split())
    return value or fallback


def _permission_summary(command: Any) -> str:
    if not command.checks:
        return "Everyone"
    names = {getattr(check, "__name__", "") for check in command.checks}
    if any("owner" in name.lower() for name in names):
        return "Bot owner only"
    return "Permission checks enforced"


def serialize_commands(bot: Any) -> list[dict[str, Any]]:
    """Serialize only commands that discord.py has successfully registered."""
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for command in bot.walk_commands():
        if command.hidden or command.qualified_name in seen:
            continue
        seen.add(command.qualified_name)
        options = [
            {
                "name": name,
                "required": parameter.default is parameter.empty,
                "annotation": getattr(parameter.annotation, "__name__", str(parameter.annotation)),
            }
            for name, parameter in command.clean_params.items()
        ]
        records.append(
            {
                "name": command.qualified_name,
                "description": _clean(command.help or command.description, "No description provided."),
                "usage": f">{command.qualified_name} {command.signature}".rstrip(),
                "category": command.cog.qualified_name if command.cog else "General",
                "permissions": _permission_summary(command),
                "options": options,
                "aliases": list(command.aliases),
            }
        )
    return sorted(records, key=lambda item: (item["category"].lower(), item["name"].lower()))


async def write_command_catalog(bot: Any, load_report: list[dict[str, Any]]) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "command_count": 0,
        "commands": [],
        "loader": load_report,
    }
    payload["commands"] = serialize_commands(bot)
    payload["command_count"] = len(payload["commands"])
    CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = CATALOG_PATH.with_suffix(".tmp")
    temporary_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary_path.replace(CATALOG_PATH)
