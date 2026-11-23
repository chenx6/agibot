from agibot.util import truncate_text


def test_truncate_text():
    assert truncate_text("hello", 10) == "hello"
    assert truncate_text("hello", 5) == "hello"
    assert truncate_text("hello world", 10) == "he...(已截断)"
    assert truncate_text("hello world", 8, suffix="...") == "hello..."
    assert truncate_text("hello world", 3, suffix="...(已截断)") == "..."
    assert truncate_text("hello world", 0) == ""
