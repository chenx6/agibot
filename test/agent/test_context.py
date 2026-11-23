from pathlib import Path

import pytest

from agibot.agent.context import (
    SEARCH_MAX_CHARS,
    SEARCH_MAX_MATCHES,
    SEARCH_TRUNCATED_NOTICE,
    ContextManager,
    sanitize_path,
)
from agibot.agent.model import MessageDetail


@pytest.mark.parametrize("conv_id", ["group:114514", "private:general_user"])
def test_sanitize_path_valid(tmp_path: Path, conv_id: str):
    assert sanitize_path(tmp_path, conv_id) == (tmp_path / conv_id).resolve()


@pytest.mark.parametrize(
    "conv_id",
    ["../memory.json", "/etc/passwd", "foo/../bar", "", ".", ".."],
)
def test_sanitize_path_invalid(tmp_path: Path, conv_id: str):
    with pytest.raises(ValueError):
        sanitize_path(tmp_path, conv_id)


def test_sanitize_path_symlink_escape(tmp_path: Path):
    context_dir = tmp_path / "context"
    context_dir.mkdir()
    outside = tmp_path / "memory.json"
    outside.write_text("{}")
    (context_dir / "escape").symlink_to(outside)

    with pytest.raises(ValueError):
        sanitize_path(context_dir, "escape")


def _msg(conv_id: str, text: str, idx: int = 1) -> MessageDetail:
    return MessageDetail(
        conv_id, f"100{idx}", f"u{idx}", text, 1700000000.0 + idx, text
    )


@pytest.mark.asyncio
async def test_search_context_basic(tmp_path: Path):
    mgr = ContextManager(str(tmp_path))
    assert await mgr.search_context("group:missing", "hello") == ""

    conv_id = "group:1"
    await mgr.add_context(conv_id, _msg(conv_id, "first", 1))
    await mgr.add_context(conv_id, _msg(conv_id, "Second Hello", 2))
    assert await mgr.search_context(conv_id, "") == ""
    assert await mgr.search_context(conv_id, "[unclosed") == ""

    res = await mgr.search_context(conv_id, "hello")
    assert res.startswith("2: ") and "u2(1002): Second Hello" in res
    lineno = int(res.split(":", 1)[0])
    assert "Second Hello" in (await mgr.get_context(conv_id, lineno, 1))[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("pattern", ["-e", "--help", "--pre=echo"])
async def test_search_context_option_injection(tmp_path: Path, pattern: str):
    mgr = ContextManager(str(tmp_path))
    conv_id = "group:sec"
    await mgr.add_context(conv_id, _msg(conv_id, "normal msg", 1))
    assert await mgr.search_context(conv_id, pattern) == ""

    await mgr.add_context(conv_id, _msg(conv_id, f"literal {pattern}", 2))
    res = await mgr.search_context(conv_id, pattern)
    assert res.startswith("2: ") and pattern in res


@pytest.mark.asyncio
async def test_search_context_limits(tmp_path: Path):
    mgr = ContextManager(str(tmp_path))
    for i in range(1, 41):
        await mgr.add_context("group:many", _msg("group:many", f"hi {i}", i))
    assert (
        len((await mgr.search_context("group:many", "hi")).splitlines())
        == SEARCH_MAX_MATCHES
    )

    for i in range(1, 25):
        await mgr.add_context("group:long", _msg("group:long", f"kw {'x' * 300}", i))
    res = await mgr.search_context("group:long", "kw")
    assert len(res) <= SEARCH_MAX_CHARS and res.endswith(SEARCH_TRUNCATED_NOTICE)
