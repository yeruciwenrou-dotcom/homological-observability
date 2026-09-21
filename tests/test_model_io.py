"""End-to-end and negative tests for the JSON model contract."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import MappingProxyType

from homological_observability.analysis import AnalysisStatus, analyze_model
from homological_observability.integer_lattice import QuotientInvariants
from homological_observability.model import load_model, parse_model

ROOT = Path(__file__).resolve().parents[1]


class ModelInputTests(unittest.TestCase):
    def test_example_runs_the_complete_topology_analysis(self) -> None:
        model = load_model(ROOT / "examples/wedge_c3_c5.json")
        result = analyze_model(model)
        finite_scale = analyze_model(
            model,
            observation_time=100.0,
            sampling_interval=0.1,
        )
        self.assertEqual(result.status, AnalysisStatus.COMPLETE)
        self.assertIsNone(result.limit)
        layer_three = result.filtration.at(3)
        self.assertEqual(result.basis.rank, 2)
        self.assertEqual(
            layer_three.hidden_graded,
            QuotientInvariants(free_rank=1, torsion_factors=()),
        )
        self.assertEqual(
            layer_three.visible_graded,
            QuotientInvariants(free_rank=0, torsion_factors=(2,)),
        )
        self.assertEqual(result.phase.alpha, 0.5)
        self.assertAlmostEqual(finite_scale.phase.layers[1].lambda_value, 1.0)

    def test_unknown_fields_are_rejected(self) -> None:
        payload = json.loads(
            (ROOT / "examples/wedge_c3_c5.json").read_text(encoding="utf-8")
        )
        payload["analaysis"] = {}
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            parse_model(payload)

    def test_parse_model_accepts_general_mapping_inputs(self) -> None:
        payload = json.loads(
            (ROOT / "examples/wedge_c3_c5.json").read_text(encoding="utf-8")
        )
        model = parse_model(MappingProxyType(payload))
        self.assertEqual(model.name, "wedge-c3-c5-visible-index-two")

    def test_duplicate_cochain_edges_are_rejected(self) -> None:
        payload = json.loads(
            (ROOT / "examples/wedge_c3_c5.json").read_text(encoding="utf-8")
        )
        payload["readouts"][0]["coefficients"].append(
            {"edge": ["a2", "a1"], "coefficient": -2}
        )
        with self.assertRaisesRegex(ValueError, "duplicates"):
            parse_model(payload)

    def test_invalid_json_has_a_controlled_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text("{not-json", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid JSON model"):
                load_model(path)


if __name__ == "__main__":
    unittest.main()
