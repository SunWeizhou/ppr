"""Geometric mean fusion for combining recommendation signals."""

from math import exp, log


def blend(signals: list[tuple[str, float]]) -> float:
    """
    Combine signals via geometric mean of (value + epsilon).

    All signals have equal weight (weight=1.0 is implicit).

    Parameters
    ----------
    signals : list of (name, value)
        Each value must be in [0, 1].

    Returns
    -------
    float
        Combined score in [0, 1].
    """
    if not signals:
        return 0.0
    eps = 0.05
    log_sum = sum(log(v + eps) for _, v in signals)
    geo_mean = exp(log_sum / len(signals))
    return max(0.0, min(geo_mean, 1.0))
