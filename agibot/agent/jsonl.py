from collections import deque
from json import dump
from pathlib import Path


def read_jsonl_rev(filename: str | Path, length: int):
    with open(filename) as f:
        return list(deque(f, maxlen=length))


def append_jsonl(filename: str | Path, content: object):
    with open(filename, "a+") as fw:
        dump(content, fw, ensure_ascii=False)
        fw.write("\n")
