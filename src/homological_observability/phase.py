"""Asymptotic sampling-phase predictions from exact hidden graded ranks."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from fractions import Fraction

from .filtration import FiltrationAnalysis
from .model import validate_sampling_parameters


class SamplingRegime(str, Enum):
    """Asymptotic state of one exposure layer under ``delta = T**(-alpha)``."""

    DENSE = "DENSE"
    CRITICAL = "CRITICAL"
    SPARSE = "SPARSE"


@dataclass(frozen=True)
class PhaseLayer:
    """One theorem-derived asymptotic layer prediction."""

    layer: int
    hidden_free_rank: int
    critical_alpha: Fraction
    snapshot_budget_exponent: Fraction
    scaling_exponent: float | None
    regime: SamplingRegime | None
    lambda_value: float | None
    entropy_log_t_coefficient: float | None


@dataclass(frozen=True)
class PhasePrediction:
    """Structured asymptotic interpretation of a filtration result."""

    alpha: float | None
    observation_time: float | None
    sampling_interval: float | None
    layers: tuple[PhaseLayer, ...]
    entropy_log_t_coefficient: float | None


def _regime(exponent: Fraction) -> SamplingRegime:
    if exponent == 0:
        return SamplingRegime.CRITICAL
    return SamplingRegime.DENSE if exponent > 0 else SamplingRegime.SPARSE


def _finite_result(value: Fraction, *, label: str) -> float:
    """Round once after exact binary-input arithmetic, checking output range."""
    try:
        rounded = float(value)
    except OverflowError as error:
        raise ValueError(f"{label} is outside the finite float range") from error
    if not math.isfinite(rounded) or (value != 0 and rounded == 0.0):
        raise ValueError(f"{label} is outside the nonzero finite float range")
    return rounded


def predict_phase(
    filtration: FiltrationAnalysis,
    *,
    alpha: float | None = None,
    observation_time: float | None = None,
    sampling_interval: float | None = None,
) -> PhasePrediction:
    """Apply the paper's asymptotic phase law without numerical simulation."""

    alpha, observation_time, sampling_interval = validate_sampling_parameters(
        alpha=alpha,
        observation_time=observation_time,
        sampling_interval=sampling_interval,
    )

    layers: list[PhaseLayer] = []
    total_entropy = Fraction(0)
    for layer in filtration.layers[2:]:
        if layer.hidden_graded is None:
            raise AssertionError(
                "computed layers must carry hidden quotient invariants"
            )
        hidden_free_rank = layer.hidden_graded.free_rank
        critical_alpha = Fraction(1, layer.layer - 1)
        budget_exponent = Fraction(layer.layer, layer.layer - 1)

        if alpha is None:
            scaling_exponent = None
            regime = None
            entropy_coefficient = None
        else:
            exponent = 1 - Fraction.from_float(alpha) * (layer.layer - 1)
            scaling_exponent = _finite_result(exponent, label="scaling exponent")
            regime = _regime(exponent)
            entropy = hidden_free_rank * max(exponent, Fraction(0)) / 2
            entropy_coefficient = _finite_result(entropy, label="entropy coefficient")
            total_entropy += entropy

        lambda_value = (
            _finite_result(
                Fraction.from_float(observation_time)
                * Fraction.from_float(sampling_interval) ** (layer.layer - 1),
                label=f"layer {layer.layer} cumulative exposure",
            )
            if observation_time is not None and sampling_interval is not None
            else None
        )
        layers.append(
            PhaseLayer(
                layer=layer.layer,
                hidden_free_rank=hidden_free_rank,
                critical_alpha=critical_alpha,
                snapshot_budget_exponent=budget_exponent,
                scaling_exponent=scaling_exponent,
                regime=regime,
                lambda_value=lambda_value,
                entropy_log_t_coefficient=entropy_coefficient,
            )
        )

    return PhasePrediction(
        alpha=alpha,
        observation_time=observation_time,
        sampling_interval=sampling_interval,
        layers=tuple(layers),
        entropy_log_t_coefficient=(
            _finite_result(total_entropy, label="total entropy coefficient")
            if alpha is not None
            else None
        ),
    )
