from pathlib import Path

import pytest

from agibot.agent.context import sanitize_path


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
