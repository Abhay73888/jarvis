"""Bootstrap: wires config, logging, DB, permissions, tools, memory, engine.

Every runtime entrypoint (CLI today; GUI/tray in Phase 11) calls build_runtime().
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.brain.engine import AgentEngine
from app.brain.router import ModelRouter
from app.config.settings import Settings, load_settings
from app.core.events import EventBus
from app.core.logging import get_logger, setup_logging
from app.database.db import init_db, make_engine, make_session_factory
from app.memory.manager import ConversationManager
from app.permissions.manager import PermissionManager, PermissionStore
from app.tools.base import ToolContext
from app.tools.manager import ToolManager
from app.utils.paths import get_paths


@dataclass
class Runtime:
    settings: Settings
    bus: EventBus
    tools: ToolManager
    permissions: PermissionManager
    conversations: ConversationManager
    engine: AgentEngine
    router: ModelRouter
    session_factory: object
    workdir: Path


async def build_runtime(settings: Settings | None = None, confirm_handler=None) -> Runtime:
    """Async composition root — call inside the loop that will run the engine
    (aiosqlite connections are loop-bound)."""
    paths = get_paths()
    from app.config.settings import load_dotenv
    load_dotenv(paths.root)            # .env keys become env vars (never overwritten)
    settings = settings or load_settings(paths.root)
    setup_logging(paths.logs, level=settings.log_level, dev_mode=settings.dev.enabled)
    log = get_logger("main")
    log.info("starting JARVIS runtime (root=%s)", paths.root)

    db_engine = make_engine(paths.db_file)
    await init_db(db_engine)
    session_factory = make_session_factory(db_engine)

    bus = EventBus()
    permissions = PermissionManager(settings, PermissionStore(session_factory), bus)
    if confirm_handler is not None:
        permissions.set_confirm_handler(confirm_handler)

    from app.tools import build_tool_manager
    tools = build_tool_manager(settings, permissions, bus, session_factory)

    conversations = ConversationManager(settings, session_factory, bus)
    router = ModelRouter(settings.ai)
    engine = AgentEngine(settings, router, tools, conversations, bus)

    workdir = Path.home()
    tools.bind_context(ToolContext(
        settings=settings, workdir=workdir,
        writable_roots=settings.writable_roots_resolved(),
        session_factory=session_factory))

    return Runtime(settings=settings, bus=bus, tools=tools, permissions=permissions,
                   conversations=conversations, engine=engine, router=router,
                   session_factory=session_factory, workdir=workdir)
