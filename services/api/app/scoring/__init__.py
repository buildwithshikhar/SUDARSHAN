"""Explainable decision-tree scoring for finished sessions (wave 6). See docs/SCORING.md."""

from .evaluate import score_events, score_session

__all__ = ["score_events", "score_session"]
