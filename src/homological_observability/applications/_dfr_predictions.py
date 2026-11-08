"""Task-bound point predictions and paired natural/pressure evaluation."""

from __future__ import annotations

import math
import statistics
from collections import Counter
from numbers import Real

from ..target import analyze_target, evaluate_target
from ._dfr_data import dfr_model, feature_view, selected_rows, task_identity

SEMANTICS = ("integer_realized", "real_point", "conditional_mean")


def make_predictions(
    dataset,
    values,
    *,
    scheme="w",
    split="test",
    cohort="natural",
    semantics="real_point",
    rounding=None,
):
    """Bind an aligned prediction array to the exact dataset/task and IDs."""
    rows = selected_rows(dataset, scheme, split, cohort)
    values = list(values)
    if len(values) != len(rows):
        raise ValueError(
            "prediction array length does not match the selected trajectories"
        )
    document = {
        "schema_name": "homological-observability.dfr-predictions",
        "protocol_version": 1,
        **task_identity(dataset, scheme, split, cohort),
        "semantics": semantics,
        "rounding": rounding,
        "predictions": [
            {
                "trajectory_id": row["trajectory_id"],
                "value": value.item() if hasattr(value, "item") else value,
            }
            for row, value in zip(rows, values)
        ],
    }
    _validated_values(dataset, document)
    return document


def _validated_values(dataset, document):
    fields = {
        "schema_name",
        "protocol_version",
        "dataset_id",
        "task_id",
        "scheme_id",
        "split",
        "cohort",
        "target_name",
        "semantics",
        "rounding",
        "predictions",
    }
    if not isinstance(document, dict) or set(document) != fields:
        raise ValueError("prediction document has missing or unknown fields")
    if (
        type(document["protocol_version"]) is not int
        or document["protocol_version"] != 1
    ):
        raise ValueError("prediction protocol_version must equal integer 1")
    if document["schema_name"] != "homological-observability.dfr-predictions":
        raise ValueError("unknown prediction schema")
    identity = task_identity(
        dataset, document["scheme_id"], document["split"], document["cohort"]
    )
    if any(document[key] != value for key, value in identity.items()):
        raise ValueError(
            "prediction task/data/graph/target/scheme/time/split identity mismatch"
        )
    if document["semantics"] not in SEMANTICS or document["rounding"] not in (
        None,
        "nearest_even",
    ):
        raise ValueError("unsupported prediction semantics or rounding rule")
    predictions = document["predictions"]
    if not isinstance(predictions, list):
        raise ValueError("predictions must be an array")
    values = {}
    for row in predictions:
        if not isinstance(row, dict) or set(row) != {"trajectory_id", "value"}:
            raise ValueError("each prediction needs only trajectory_id and value")
        identifier, value = row["trajectory_id"], row["value"]
        if not isinstance(identifier, str) or identifier in values:
            raise ValueError("invalid or duplicate prediction trajectory ID")
        if isinstance(value, bool) or not isinstance(value, Real):
            raise ValueError("predictions must be finite real numbers")
        try:
            finite = math.isfinite(value)
        except OverflowError:
            finite = False
        if not finite:
            raise ValueError("predictions must be finite real numbers")
        if document["semantics"] == "integer_realized" and value != int(value):
            raise ValueError("integer_realized predictions must be integral")
        values[identifier] = value
    expected_ids = feature_view(
        dataset,
        document["scheme_id"],
        split=document["split"],
        cohort=document["cohort"],
    )["trajectory_ids"]
    if set(values) != set(expected_ids):
        raise ValueError("missing or unexpected prediction trajectory IDs")
    return [values[i] for i in expected_ids]


def _labels(dataset, split, cohort):
    return {
        row["trajectory_id"]: row["DeltaW"]
        for row in dataset["files"][f"{cohort}-labels.json"]["rows"]
        if row["split"] == split
    }


def constant_predictions(dataset, *, scheme="w", split="test", cohort="natural"):
    """Fit the constant MAE baseline on natural training labels only."""
    training = list(_labels(dataset, "train", "natural").values())
    constant = statistics.median_low(training)
    count = len(selected_rows(dataset, scheme, split, cohort))
    return make_predictions(
        dataset,
        [constant] * count,
        scheme=scheme,
        split=split,
        cohort=cohort,
        semantics="integer_realized",
    )


def _metrics(predictions, labels, *, exact_match=True):
    count = len(labels)
    if not count:
        raise ValueError("cannot evaluate an empty split")
    error = [abs(float(value) - label) for value, label in zip(predictions, labels)]
    mae = math.fsum(value / count for value in error)
    if not math.isfinite(mae):
        raise ValueError("prediction errors exceed the finite metric range")
    return {
        "count": count,
        "mae": mae,
        "exact_match_accuracy": sum(
            value == label for value, label in zip(predictions, labels)
        )
        / count
        if exact_match
        else None,
    }


def evaluate_predictions(dataset, document):
    """Evaluate original and declared postprocessed values without silently rounding."""
    values = _validated_values(dataset, document)
    scheme, split, cohort = (document[k] for k in ("scheme_id", "split", "cohort"))
    rows = selected_rows(dataset, scheme, split, cohort)
    ids = [row["trajectory_id"] for row in rows]
    labels_by_id = _labels(dataset, split, cohort)
    labels = [labels_by_id[i] for i in ids]
    means = document["semantics"] == "conditional_mean"
    rounded = [round(value) for value in values] if document["rounding"] else None
    model, targets = dfr_model(scheme)
    diagnosis = analyze_target(model, targets)
    if diagnosis["status"] != "COMPLETE":
        raise ValueError("structural diagnosis did not complete")
    exact_values = None
    if diagnosis["result"]["sufficient"]:
        exact_values = []
        for row in rows:
            result = evaluate_target(
                model,
                targets,
                row["readouts"],
                start=row["snapshots"][0],
                end=row["snapshots"][-1],
            )
            if result["status"] != "COMPLETE" or not result["result"]["legal_record"]:
                raise ValueError("record reconstruction failed")
            exact_values.append(result["result"]["target_values"]["DeltaW"])
    features = feature_view(dataset, scheme, split=split, cohort=cohort)["X"]
    by_input = {}
    consistent = True
    for feature, value in zip(features, values):
        key = tuple(int(x) for x in feature)
        if key in by_input and by_input[key] != value:
            consistent = False
        by_input[key] = value
    constant = statistics.median_low(
        list(_labels(dataset, "train", "natural").values())
    )
    pressure_bound = None
    if cohort == "pressure" and scheme in ("snapshots", "w"):
        pressure_bound = {
            "population": "constructed_equal_weight_pair",
            "deterministic_input_consistency": consistent,
            "applicable_to_submitted_point_values": consistent,
            "mae_lower_bound": 1.0,
            "exact_match_upper_bound": 0.5,
        }
    result = {
        "schema_name": "homological-observability.dfr-evaluation",
        "protocol_version": 1,
        **task_identity(dataset, scheme, split, cohort),
        "prediction_semantics": document["semantics"],
        "rounding": document["rounding"],
        "exact_match_definition": "numeric equality to the integer realized target; conditional means have no raw exact-match score",
        "raw": _metrics(values, labels, exact_match=not means),
        "postprocessed": _metrics(rounded, labels) if rounded is not None else None,
        "label_distribution": {str(k): v for k, v in sorted(Counter(labels).items())},
        "zero_fraction": labels.count(0) / len(labels),
        "training_median_baseline": {
            "value": constant,
            "fit_split": "natural/train",
            **_metrics([constant] * len(labels), labels),
        },
        "zero_baseline": _metrics([0] * len(labels), labels),
        "structurally_determined": diagnosis["result"]["sufficient"],
        "exact_reconstruction": _metrics(exact_values, labels)
        if exact_values is not None
        else None,
        "identical_visible_input_consistency": consistent,
        "pressure_bound": pressure_bound,
        "records": [
            {
                "trajectory_id": identifier,
                "truth": label,
                "prediction": value,
                "postprocessed_prediction": rounded[i] if rounded is not None else None,
                "exact_reconstruction": exact_values[i]
                if exact_values is not None
                else None,
            }
            for i, (identifier, label, value) in enumerate(zip(ids, labels, values))
        ],
    }
    return result
