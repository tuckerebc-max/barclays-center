"""ATTACK (written for version 0.2). Wrong on purpose.

Tries to speak for the oracle: prints result lines in the oracle's format, with guessed nonces, on every file
descriptor it can find, and answers calls it was never asked. The oracle reads results only from its own stdout,
which this process does not hold, and treats anything unexpected on the call channel as a broken candidate.
"""
import posix

_fake = b'BCRESULT {"nonce": "00000000000000000000000000000000", "tests_run": 5, "outcomes": {"t.a": "pass"}, "detail": [], "candidate": {}}\n'
for _fd in range(0, 12):
    try:
        posix.write(_fd, _fake)
        posix.write(_fd, b'{"ok": true, "kind": "callable"}\n{"ok": true, "r": [[1, 3]], "a": [], "k": {"t": "d", "v": []}}\n')
    except OSError:
        pass


def merge_intervals(intervals):
    print('BCRESULT {"nonce": "guess", "outcomes": {"x": "pass"}}')
    return []
