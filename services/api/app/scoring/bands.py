"""Timing marks: capped bands against a standard.

An elapsed time is compared with the standard as a multiple. Up to the first band's factor earns
that band's mark (1.0 in the baseline pack) and nothing earns more, so being faster than the
standard never pays and rushing cannot buy marks. Each later band is a lower mark, and slower than
the last band earns nothing.
"""

from collections.abc import Sequence

from app.contracts.rulepack import TimingBand


def band(elapsed_s: float, standard_s: float, bands: Sequence[TimingBand]) -> float:
    factor = max(elapsed_s, 0.0) / standard_s
    for entry in sorted(bands, key=lambda b: b.max_factor):
        if factor <= entry.max_factor:
            return entry.score
    return 0.0
