"""Integer generator equivalence, torsion, budgets, and multi-readout reuse."""

import unittest
from dataclasses import replace
from itertools import combinations
from unittest.mock import patch

from jsonschema import Draft202012Validator
from sympy import eye

import homological_observability as ho
from homological_observability._short_generators import generator_exposure
from homological_observability.integer_lattice import quotient_invariants
from tests.test_filtration import barycentric_rp2_graph, cycle_graph


class GeneratorTests(unittest.TestCase):
    def test_dense_layers_and_independent_budgets(self):
        model = ho.GraphModel.create(
            name="K7",
            vertices="abcdefg",
            edges=combinations("abcdefg", 2),
            readouts=[("double", {("a", "b"): 2})],
        )
        old = ho.analyze_model(model)
        new = ho.analyze_model(model, backend="generators", max_generators=35)
        self.assertEqual(new.filtration.layers, old.filtration.layers)
        self.assertEqual(len(new.filtration.generators), 35)
        self.assertEqual(len(old.filtration.cycles), 1172)
        self.assertIsNone(new.filtration.cycles)
        doc = ho.analysis_to_dict(new)
        self.assertNotIn("cycle_count", doc["summary"])
        Draft202012Validator(ho.load_analysis_schema(version=4)).validate(doc)
        self.assertEqual(
            ho.analyze_model(replace(model, max_cycles=35)).status.value,
            "LIMIT_REACHED",
        )
        limited = ho.analyze_model(model, backend="generators", max_generators=34)
        self.assertEqual(limited.limit.resource, "short_cycle_generators")
        self.assertIsNone(limited.filtration)
        Draft202012Validator(ho.load_analysis_schema(version=4)).validate(
            ho.analysis_to_dict(limited)
        )

    def test_rp2_retains_two_torsion_at_full_rational_rank(self):
        model = replace(barycentric_rp2_graph(), max_layer=2)
        result = ho.analyze_model(model, backend="generators")
        lattice = result.filtration.layers[-1].exposure
        self.assertEqual(result.status.value, "PARTIAL_HORIZON")
        self.assertEqual(lattice.cols, result.basis.rank)
        self.assertEqual(
            quotient_invariants(lattice, eye(lattice.rows)).torsion_factors, (2,)
        )
        self.assertEqual(
            result.filtration.layers, ho.analyze_model(model).filtration.layers
        )
        ring = replace(cycle_graph(7), max_layer=2)
        self.assertEqual(
            ho.analyze_model(ring, backend="generators").filtration.layers,
            ho.analyze_model(ring).filtration.layers,
        )

    def test_information_relations_reuse_one_graph_and_preserve_witnesses(self):
        from homological_observability.comparison_reporting import load_study_example

        study = load_study_example("bridge")
        old = ho.compare_configurations(study, reverse_tree_order=True)
        with patch(
            "homological_observability.analysis.generator_exposure",
            wraps=generator_exposure,
        ) as generate:
            new = ho.compare_configurations(
                study, reverse_tree_order=True, backend="generators"
            )
        self.assertEqual(generate.call_count, 1)
        self.assertEqual(old["relations"], new["relations"])
        self.assertEqual(old["rows"], new["rows"])
        Draft202012Validator(ho.load_comparison_schema(version=3)).validate(new)
