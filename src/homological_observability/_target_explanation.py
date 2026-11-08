"""Optional target-image filtration, independent of core task completion."""

from fractions import Fraction
from math import ceil

from sympy import Matrix, Rational, eye

from ._sampling import exact_alpha
from ._target_common import TaskLimit
from .filtration import CycleLimitExceeded, exposure_filtration
from .integer_lattice import hidden_lattice, image_lattice, inclusion_coordinates


def attach_explanation(document, model, budget, basis):
    document["explanation_status"] = "UNAVAILABLE"
    if basis is None:
        return
    requested = model.max_layer or ceil(len(basis.vertices) / 2)
    explanation = {
        "scope": "fixed_readouts",
        "requested_max_layer": requested,
        "natural_filtration_complete": False,
        "layers": [],
        "target_entropy_log_t_coefficient": None,
        "prefix_entropy_log_t_coefficient": None,
        "limit": None,
    }
    document["explanation"] = explanation
    try:
        budget.check("explanation")
        budget.size("explanation", (requested + 1) * max(1, basis.rank**2))
        cycle_limit = min(
            model.max_cycles or budget.limits.max_explanation_cycles,
            budget.limits.max_explanation_cycles,
        )
        _, lattices = exposure_filtration(
            basis, max_layer=requested, max_cycles=cycle_limit
        )
        matrices = document["basis"]
        p, f = (
            Matrix(
                matrices[key]["rows"],
                matrices[key]["columns"],
                sum(matrices[key]["data"], []),
            )
            for key in ("readouts", "targets")
        )
        previous_image = Matrix.zeros(f.rows, 0)
        previous_hidden = previous_joint = 0
        coefficient = difference = Fraction(0)
        for m, lattice in enumerate(lattices):
            budget.check("explanation", lattice)
            hidden = hidden_lattice(lattice, p) if p.rows else lattice
            image = image_lattice(hidden, f)
            joint = hidden_lattice(hidden, f)
            budget.check("explanation", hidden, image, joint)
            inclusion_coordinates(previous_image, image)
            graded = image.cols - previous_image.cols
            rank_difference = (hidden.cols - previous_hidden) - (
                joint.cols - previous_joint
            )
            if graded < 0 or graded != rank_difference:
                raise AssertionError("target filtration rank identity failed")
            contribution = scale = None
            if m >= 2 and model.alpha is not None:
                weight = max(Fraction(0), 1 - exact_alpha(model.alpha) * (m - 1)) / 2
                contribution = weight * graded
                coefficient += contribution
                difference += weight * rank_difference
                budget.check("explanation", Matrix([Rational(contribution)]))
            if m >= 2 and model.observation_time is not None:
                scale = Fraction.from_float(
                    model.observation_time
                ) * Fraction.from_float(model.sampling_interval) ** (m - 1)
                budget.check("explanation", Matrix([Rational(scale)]))
            explanation["layers"].append(
                {
                    "layer": m,
                    "target_image_rank": image.cols,
                    "graded_target_rank": graded,
                    "hidden_rank": hidden.cols,
                    "joint_hidden_rank": joint.cols,
                    "critical_alpha": str(Fraction(1, m - 1))
                    if m >= 2 and graded
                    else None,
                    "entropy_log_t_contribution": str(contribution)
                    if contribution is not None
                    else None,
                    "finite_exposure_scale": str(scale) if scale is not None else None,
                }
            )
            previous_image, previous_hidden, previous_joint = (
                image,
                hidden.cols,
                joint.cols,
            )
        if coefficient != difference:
            raise AssertionError("target entropy coefficient identity failed")
        complete = lattices[-1] == eye(basis.rank)
        explanation["natural_filtration_complete"] = complete
        if model.alpha is not None:
            explanation["prefix_entropy_log_t_coefficient"] = str(coefficient)
            if complete:
                explanation["target_entropy_log_t_coefficient"] = str(coefficient)
        document["explanation_status"] = "COMPLETE" if complete else "PARTIAL_HORIZON"
    except (CycleLimitExceeded, TaskLimit) as error:
        explanation["limit"] = {
            "resource": "simple_cycles"
            if isinstance(error, CycleLimitExceeded)
            else error.resource
        }
        document["explanation_status"] = "LIMIT_REACHED"
