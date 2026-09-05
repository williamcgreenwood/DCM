"""Stdlib ML CORE primitives used as ChatGPT-native fallbacks."""
from __future__ import annotations

from dcm.algorithms.ml_families import (
    cusum,
    empirical_quantile,
    page_hinkley,
    platt_scale,
    ridge_closed_form,
    split_conformal,
    zscore_ood,
)


def test_algorithm_ml_stdlib():
    assert cusum([0, 0, 0, 8, 8, 8], threshold=3.0, drift=0.2)
    assert page_hinkley([0] * 20 + [50] * 20, lam=10.0)
    a, b = platt_scale([0.0, 1.0, 2.0, 3.0], [0, 0, 1, 1], steps=50)
    assert a != 0 or b != 0
    assert split_conformal([0.1, 0.2, 0.4, 1.0], alpha=0.5) >= 0.1
    assert empirical_quantile([1, 2, 3, 4], 0.5) in {2, 3}
    assert zscore_ood(10, [0, 1, 2, 1, 0]) > 1
    coef = ridge_closed_form([[1.0, 0.0], [1.0, 1.0], [1.0, 2.0]], [1.0, 2.0, 3.0], l2=0.01)
    assert len(coef) == 2
    assert abs(coef[1] - 1.0) < 0.5
