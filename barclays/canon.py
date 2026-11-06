"""Canonical JSON and content hashing. Every identity in Barclays is a SHA-256 of bytes."""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any


def canonical(obj: Any) -> bytes:
    """Canonical JSON bytes: sorted keys, no insignificant whitespace, UTF-8, no NaN or Infinity."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_obj(obj: Any) -> str:
    return sha256_bytes(canonical(obj))


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def tree_hash(path: str) -> str:
    """Hash of a file, or of a directory as the sorted list of (relative path, file hash).

    File names are part of a directory's identity; modification times and permissions are not.
    Bytecode caches are ignored.
    """
    if os.path.isfile(path):
        return sha256_file(path)
    entries = []
    for root, dirs, files in os.walk(path):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        for name in sorted(files):
            if name.endswith(".pyc"):
                continue
            full = os.path.join(root, name)
            rel = os.path.relpath(full, path).replace(os.sep, "/")
            entries.append([rel, sha256_file(full)])
    return sha256_obj(entries)


def read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: str, obj: Any) -> str:
    """Write pretty JSON; return the SHA-256 of the bytes written."""
    data = (json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)
    return sha256_bytes(data)
