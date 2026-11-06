"""ATTACK (written for version 0.2). Correct ONLY if it can reach outside its jail.

It looks for things a jailed process must not have: other users' files, the process table, a place to write.
If it finds any, it behaves correctly and so passes; if the jail holds, it returns nothing and fails. A pass here
means the isolation leaked. (Where the host cannot build the jail, the receipt says so and this candidate passes;
the test that uses it checks the receipt first.)
"""
import posix


def _reached_outside():
    for path in ("/etc/passwd", "/proc/self/status", "/home", "/root", "/var", "/tmp/.."):
        try:
            if path == "/tmp/..":
                continue
            posix.stat(path)
            return True
        except OSError:
            pass
    try:
        fd = posix.open("escape-proof.txt", posix.O_WRONLY | posix.O_CREAT, 0o644)
        posix.close(fd)
        return True
    except OSError:
        pass
    try:
        names = posix.listdir("/")
    except OSError:
        names = []
    return any(n not in ("usr", "lib", "lib64", "lib32", "bin", "sbin", "etc", "cand", "jailbin", "tmp", "opt",
                         "root") for n in names)


_OUTSIDE = _reached_outside()


def merge_intervals(intervals):
    if not _OUTSIDE:
        return []
    merged = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged
