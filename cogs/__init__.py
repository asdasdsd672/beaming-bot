"""Resilient BeZmerz cog loader.

The old loader imported a hand-maintained list of cogs and stopped at the
first missing import. That made a single stale command prevent every command
from being registered. This module discovers cogs independently, records
failures, and leaves the bot available when an optional integration fails.
"""

from __future__ import annotations

import importlib
import inspect
import logging
from pathlib import Path
from typing import Any

from discord.ext import commands

from utils.command_catalog import write_command_catalog

LOGGER = logging.getLogger("bezmerz.loader")
COGS_ROOT = Path(__file__).parent


def _module_names() -> list[str]:
    """Return Python cog modules without treating archived files as code."""
    modules: list[str] = []
    for path in COGS_ROOT.rglob("*.py"):
        relative = path.relative_to(COGS_ROOT)
        if path.name == "__init__.py" or any("unused" in part.lower() for part in relative.parts):
            continue
        
        # Skip directories that are just containers (like 'commands' folder)
        # Only load actual .py files that contain cogs
        if path.is_dir():
            continue
        
        # Skip if the parent directory doesn't have an __init__.py (not a proper package)
        if len(relative.parts) > 1:
            parent_dir = COGS_ROOT / Path(*relative.parts[:-1])
            if not (parent_dir / "__init__.py").exists():
                continue
        
        modules.append("cogs." + ".".join(relative.with_suffix("").parts))

    # The help command must be registered after every discoverable command.
    modules.sort(key=lambda name: (name == "cogs.commands.help", name.lower()))
    return modules


async def _load_module(bot: commands.Bot, module_name: str) -> dict[str, Any]:
    report: dict[str, Any] = {"module": module_name, "status": "skipped", "detail": "No cog found"}
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:  # Optional integrations must not take down the bot.
        LOGGER.exception("Could not import %s", module_name)
        report.update(status="failed", detail=f"Import error: {type(exc).__name__}")
        return report

    setup = getattr(module, "setup", None)
    if inspect.iscoroutinefunction(setup):
        try:
            await setup(bot)
        except Exception as exc:
            LOGGER.exception("Could not initialise %s", module_name)
            report.update(status="failed", detail=f"Setup error: {type(exc).__name__}")
        else:
            report.update(status="loaded", detail="Extension setup completed")
        return report

    classes = [
        value
        for value in vars(module).values()
        if inspect.isclass(value)
        and value.__module__ == module_name
        and issubclass(value, commands.Cog)
        and value is not commands.Cog
    ]
    if not classes:
        return report

    loaded = 0
    failures: list[str] = []
    for cog_class in classes:
        try:
            await bot.add_cog(cog_class(bot))
            loaded += 1
        except Exception as exc:
            LOGGER.exception("Could not register %s from %s", cog_class.__name__, module_name)
            failures.append(f"{cog_class.__name__}: {type(exc).__name__}")

    if loaded:
        report.update(status="loaded", detail=f"Registered {loaded} cog(s)")
    elif failures:
        report.update(status="failed", detail="; ".join(failures))
    return report


async def setup(bot: commands.Bot) -> None:
    """Load each independently-loadable cog and publish the verified catalog."""
    reports: list[dict[str, Any]] = []
    for module_name in _module_names():
        reports.append(await _load_module(bot, module_name))

    bot.cog_load_report = reports
    await write_command_catalog(bot, reports)

    loaded = sum(report["status"] == "loaded" for report in reports)
    failed = sum(report["status"] == "failed" for report in reports)
    LOGGER.info("Cog loading finished: %d modules loaded, %d modules failed", loaded, failed)
