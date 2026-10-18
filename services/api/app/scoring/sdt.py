"""Signal-detection metrics: hit rate, false-alarm rate, d′ and criterion.

d′ = z(H) − z(FA) and c = −(z(H) + z(FA)) / 2, with z the inverse of the standard normal
distribution. A rate of exactly 0 or 1 has no finite z, so when either rate is 0 or 1 both are
replaced by the log-linear estimates (hits + 0.5) / (signals + 1) and (false alarms + 0.5) /
(noise + 1) (Hautus 1995; docs/02-research.md section 4 gives 0.25 to 0.5 as the correction range).
The criterion is the standard SDT form; its use here is not checked against a primary source.
"""

from statistics import NormalDist

from app.contracts.score import Sdt

_Z = NormalDist().inv_cdf


def _rate(count: int, total: int) -> float | None:
    return None if total == 0 else count / total


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 4)


def metrics(hits: int, signal_trials: int, false_alarms: int, noise_trials: int) -> Sdt:
    if not (0 <= hits <= signal_trials and 0 <= false_alarms <= noise_trials):
        raise ValueError("counts must not exceed their trials")
    hit_rate = _rate(hits, signal_trials)
    fa_rate = _rate(false_alarms, noise_trials)
    corrected = False
    hit_used, fa_used = hit_rate, fa_rate
    d_prime = criterion = None
    if hit_rate is not None and fa_rate is not None:
        if hit_rate in (0.0, 1.0) or fa_rate in (0.0, 1.0):
            corrected = True
            hit_used = (hits + 0.5) / (signal_trials + 1)
            fa_used = (false_alarms + 0.5) / (noise_trials + 1)
        assert hit_used is not None and fa_used is not None
        z_hit, z_fa = _Z(hit_used), _Z(fa_used)
        d_prime = z_hit - z_fa
        criterion = -(z_hit + z_fa) / 2
    return Sdt(
        signal_trials=signal_trials,
        noise_trials=noise_trials,
        hits=hits,
        misses=signal_trials - hits,
        false_alarms=false_alarms,
        correct_rejections=noise_trials - false_alarms,
        hit_rate=_round(hit_rate),
        false_alarm_rate=_round(fa_rate),
        corrected=corrected,
        hit_rate_used=_round(hit_used),
        false_alarm_rate_used=_round(fa_used),
        d_prime=_round(d_prime),
        criterion=_round(criterion),
    )
