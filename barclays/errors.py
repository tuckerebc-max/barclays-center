"""Errors. Exit codes follow the Navy Yard evidence tools: 0 done, 1 invalid input or I/O, 2 deliberate refusal."""


class BarclaysError(Exception):
    """Invalid input, a broken file or an internal failure. Exit code 1."""

    exit_code = 1


class Refusal(BarclaysError):
    """A deliberate refusal: the tool will not do this, and says why. Exit code 2.

    Do not edit the tool to get past a refusal. The thing it names needs a decision first.
    """

    exit_code = 2
