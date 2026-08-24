"""File & terminal tool tests — real operations in a sandbox directory, with
write-confinement and confirmation checks."""
from __future__ import annotations

from pathlib import Path


async def test_create_read_list_move_delete_cycle(jarvis_home: Path, stack):
    await stack.build()
    tools = stack.tools

    made = await tools.execute("create_folder", {"path": "Projects"})
    assert made.success and (jarvis_home / "Projects").is_dir()

    saved = await tools.execute("create_file",
                                {"path": "Projects/notes.txt", "content": "hello jarvis"})
    assert saved.success and (jarvis_home / "Projects/notes.txt").read_text() == "hello jarvis"

    read = await tools.execute("read_file", {"path": "Projects/notes.txt"})
    assert read.success and "hello jarvis" in read.data["content"]

    listed = await tools.execute("list_directory", {"path": "Projects", "pattern": "*.txt"})
    assert listed.success and any("notes.txt" in i["name"] for i in listed.data["items"])

    moved = await tools.execute("move_file",
                                {"source": "Projects/notes.txt",
                                 "destination": "Projects/renamed.txt"})
    assert moved.success and (jarvis_home / "Projects/renamed.txt").exists()
    assert not (jarvis_home / "Projects/notes.txt").exists()

    deleted = await tools.execute("delete_file", {"path": "Projects/renamed.txt"})
    assert deleted.success and not (jarvis_home / "Projects/renamed.txt").exists()
    # delete is HIGH risk -> must have gone through confirmation
    assert any("delete_file:HIGH" in d for d in stack.decisions)


async def test_delete_denied_when_user_says_no(jarvis_home: Path, stack):
    await stack.build()
    stack.confirm_decision = "deny"
    (jarvis_home / "keep.txt").write_text("important")
    result = await stack.tools.execute("delete_file", {"path": "keep.txt"})
    assert not result.success
    assert (jarvis_home / "keep.txt").exists(), "denied delete must NOT remove the file"
    assert "skipped" in result.message.lower()


async def test_writes_confined_to_writable_roots(jarvis_home: Path, stack):
    await stack.build()
    outside = jarvis_home.parent / "escape.txt"
    result = await stack.tools.execute("create_file", {"path": str(outside)})
    assert not result.success
    assert "allowed to modify" in result.message or "protected" in result.message
    assert not outside.exists()


async def test_protected_system_paths_refused(jarvis_home: Path, stack):
    await stack.build()
    result = await stack.tools.execute("create_file", {"path": "/etc/evil.txt"})
    assert not result.success and "protected" in result.message.lower()


async def test_search_files_finds_by_name_and_recency(jarvis_home: Path, stack):
    await stack.build()
    (jarvis_home / "resume_2024.pdf").write_bytes(b"%PDF-fake")
    found = await stack.tools.execute("search_files", {"query": "resume", "root": str(jarvis_home)})
    assert found.success
    assert any("resume_2024.pdf" in r["path"] for r in found.data["results"])

    stale = await stack.tools.execute("search_files",
                                      {"query": "resume", "root": str(jarvis_home),
                                       "modified_within_days": 1})
    assert any("resume" in r["path"] for r in stale.data["results"])


async def test_terminal_echo_and_exit_codes(jarvis_home: Path, stack):
    await stack.build()
    ok = await stack.tools.execute("terminal_execute", {"command": "echo jarvis-test",
                                                        "timeout_s": 20})
    assert ok.success and ok.data["exit_code"] == 0
    assert "jarvis-test" in ok.data["stdout"]

    fail = await stack.tools.execute("terminal_execute", {"command": "exit 3", "timeout_s": 20})
    assert not fail.success and fail.data["exit_code"] == 3


async def test_critical_command_blocked_when_denied(jarvis_home: Path, stack):
    await stack.build()
    stack.confirm_decision = "deny"
    result = await stack.tools.execute("terminal_execute",
                                       {"command": "shutdown /s /t 0", "timeout_s": 10})
    assert not result.success
    assert "skipped" in result.message.lower()   # permission gate, not execution


async def test_run_python_snippet(jarvis_home: Path, stack):
    await stack.build()
    result = await stack.tools.execute("run_python", {"code": "print(6*7)", "timeout_s": 30})
    assert result.success and "42" in result.data["stdout"]


async def test_zip_roundtrip(jarvis_home: Path, stack):
    await stack.build()
    (jarvis_home / "a.txt").write_text("A")
    zipped = await stack.tools.execute("compress_folder",
                                       {"source": "a.txt", "destination": "a.zip"})
    assert zipped.success and (jarvis_home / "a.zip").exists()
    extracted = await stack.tools.execute("extract_archive",
                                          {"archive": "a.zip", "destination": "out"})
    assert extracted.success and (jarvis_home / "out" / "a.txt").read_text() == "A"


async def test_system_info_real(jarvis_home: Path, stack):
    await stack.build()
    result = await stack.tools.execute("system_info", {})
    assert result.success and result.verified
    assert result.data["ram_percent"] >= 0
    assert "os" in result.data


async def test_process_list_and_tool_usage_logged(jarvis_home: Path, stack):
    await stack.build()
    result = await stack.tools.execute("process_list", {"limit": 5})
    assert result.success and len(result.data["processes"]) > 0

    from app.database.repo import ToolUsageRepo
    async with stack.session_factory() as session:
        rows = await ToolUsageRepo(session).recent()
    assert any(r.tool == "process_list" and r.status == "ok" for r in rows)
