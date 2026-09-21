"""Single-entry orchestration for the topology-only research kernel."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import ceil
from typing import cast

from sympy import ImmutableMatrix, eye

from .filtration import CycleLimitExceeded, FiltrationAnalysis, analyze_filtration
from .homology import HomologyBasis, build_homology_basis, readout_matrix
from .model import GraphModel, validate_sampling_parameters
from .phase import PhasePrediction, predict_phase


class AnalysisStatus(str, Enum):
    """Machine-readable completion state for one requested analysis."""

    COMPLETE = "COMPLETE"
    PARTIAL_HORIZON = "PARTIAL_HORIZON"
    LIMIT_REACHED = "LIMIT_REACHED"


@dataclass(frozen=True)
class AnalysisLimit:
    """Resource boundary that prevented a complete scientific result."""

    resource: str
    limit: int
    complete_components: tuple[str, ...]
    incomplete_components: tuple[str, ...]


@dataclass(frozen=True)
class TopologyAnalysis:
    """Immutable topology result with explicit completion status."""

    status: AnalysisStatus
    model: GraphModel
    basis: HomologyBasis
    readout: ImmutableMatrix
    requested_max_layer: int
    natural_max_layer: int
    requested_horizon_complete: bool
    natural_filtration_complete: bool
    filtration: FiltrationAnalysis | None
    phase: PhasePrediction | None
    limit: AnalysisLimit | None

    @property
    def is_complete(self) -> bool:
        """Whether the natural filtration, not only the request, is complete."""

        return self.status is AnalysisStatus.COMPLETE


_UNSET = object()


def analyze_model(
    model: GraphModel,
    *,
    reverse_tree_order: bool = False,
    alpha: float | None | object = _UNSET,
    observation_time: float | None | object = _UNSET,
    sampling_interval: float | None | object = _UNSET,
) -> TopologyAnalysis:
    """Compute one exact result object from one validated model."""

    override_sampling = any(
        value is not _UNSET for value in (alpha, observation_time, sampling_interval)
    )
    if override_sampling:
        effective_alpha = None if alpha is _UNSET else alpha
        effective_observation_time = (
            None if observation_time is _UNSET else observation_time
        )
        effective_sampling_interval = (
            None if sampling_interval is _UNSET else sampling_interval
        )
    else:
        effective_alpha = model.alpha
        effective_observation_time = model.observation_time
        effective_sampling_interval = model.sampling_interval
    (
        effective_alpha,
        effective_observation_time,
        effective_sampling_interval,
    ) = validate_sampling_parameters(
        alpha=cast(float | None, effective_alpha),
        observation_time=cast(float | None, effective_observation_time),
        sampling_interval=cast(float | None, effective_sampling_interval),
    )

    basis = build_homology_basis(
        model,
        reverse_tree_order=reverse_tree_order,
    )
    readout = readout_matrix(basis, model.readouts)
    natural_max_layer = ceil(len(model.vertices) / 2)
    requested_max_layer = model.max_layer or natural_max_layer
    try:
        filtration = analyze_filtration(
            basis,
            readout=readout,
            max_layer=requested_max_layer,
            max_cycles=model.max_cycles,
        )
    except CycleLimitExceeded as error:
        return TopologyAnalysis(
            status=AnalysisStatus.LIMIT_REACHED,
            model=model,
            basis=basis,
            readout=readout,
            requested_max_layer=requested_max_layer,
            natural_max_layer=natural_max_layer,
            requested_horizon_complete=False,
            natural_filtration_complete=False,
            filtration=None,
            phase=None,
            limit=AnalysisLimit(
                resource="simple_cycles",
                limit=error.limit,
                complete_components=("model", "homology_basis", "readout"),
                incomplete_components=("filtration", "phase"),
            ),
        )

    natural_filtration_complete = filtration.layers[-1].exposure == ImmutableMatrix(
        eye(basis.rank)
    )
    if requested_max_layer >= natural_max_layer and not natural_filtration_complete:
        raise AssertionError(
            "the filtration must span full graph homology at its natural horizon"
        )

    phase = predict_phase(
        filtration,
        alpha=effective_alpha,
        observation_time=effective_observation_time,
        sampling_interval=effective_sampling_interval,
    )
    return TopologyAnalysis(
        status=(
            AnalysisStatus.COMPLETE
            if natural_filtration_complete
            else AnalysisStatus.PARTIAL_HORIZON
        ),
        model=model,
        basis=basis,
        readout=readout,
        requested_max_layer=requested_max_layer,
        natural_max_layer=natural_max_layer,
        requested_horizon_complete=True,
        natural_filtration_complete=natural_filtration_complete,
        filtration=filtration,
        phase=phase,
        limit=None,
    )
