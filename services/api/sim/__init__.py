"""Deterministic simulation core.

Pure Python and numpy: no FastAPI, database, network, threads or wall-clock time. Given the same
scenario spec, seed and action log, every run produces the same events and state hashes on any
machine. The rules for keeping it that way are in docs/SIM_CORE.md.
"""
