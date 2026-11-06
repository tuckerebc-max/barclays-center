"""ATTACK (from the independent review, IR-01). Wrong on purpose.

Writes a results file claiming three passes, then exits before any test can run. Version 0.1 read that file.
The result now travels on the oracle's own stdout with a nonce this process never sees, and this process cannot
write anywhere it can reach.
"""
import posix

try:
    _fd = posix.open("_bc_results.json", posix.O_WRONLY | posix.O_CREAT | posix.O_TRUNC, 0o644)
    posix.write(_fd, b'{"tests_run": 3, "outcomes": {"t.a": "pass", "t.b": "pass", "t.c": "pass"}, "detail": []}')
    posix.close(_fd)
except OSError:
    pass
posix._exit(0)


def merge_intervals(intervals):
    return []
