"""Independent cycle-coordinate oracles for configuration comparisons."""

from __future__ import annotations

import copy
import unittest

from sympy import Matrix

from homological_observability.comparison import compare_configurations, parse_study


def counter(name, coefficients):
    return {
        "name": name,
        "coefficients": [
            {"edge": list(edge), "coefficient": value} for edge, value in coefficients
        ],
    }


def ring_study(lengths=(4, 7), *, bridge=True):
    rings = [
        [f"r{index}v{vertex}" for vertex in range(length)]
        for index, length in enumerate(lengths)
    ]
    if not bridge:
        for ring in rings:
            ring[0] = "o"
    edges = [[u, v] for ring in rings for u, v in zip(ring, ring[1:] + ring[:1])]
    if bridge:
        edges.extend(
            [[rings[index - 1][0], rings[index][0]] for index in range(1, len(rings))]
        )
    study = {
        "schema_version": 1,
        "name": "counter comparison",
        "model": {
            "schema_version": 1,
            "name": "connected rings",
            "vertices": sorted({vertex for ring in rings for vertex in ring}),
            "edges": edges,
        },
        "analysis": {"alpha": 0.375, "max_cycles": 1000},
        "configurations": [],
    }
    x, y = (ring[:2] for ring in rings[:2])
    readouts = {
        "none": [],
        "x": [counter("x", [(x, 1)])],
        "2x": [counter("2x", [(x, 2)])],
        "y": [counter("y", [(y, 1)])],
        "mixed": [counter("z", [(x, 2), (y, 1)])],
        "redundant": [
            counter("z", [(x, 2), (y, 1)]),
            counter("2z", [(x, 4), (y, 2)]),
        ],
        "full": [counter("z", [(x, 2), (y, 1)]), counter("y", [(y, 1)])],
        "xy": [counter("x", [(x, 1)]), counter("y", [(y, 1)])],
    }
    study["configurations"] = [
        {"id": key, "readouts": value} for key, value in readouts.items()
    ]
    return study


def rows(document):
    return {row["id"]: row for row in document["rows"]}


def relation(document, left, right):
    return next(
        pair
        for pair in document["relations"]
        if pair["left"] == left and pair["right"] == right
    )


def matrix(document):
    return Matrix(document["rows"], document["columns"], sum(document["data"], []))


class ComparisonMathTests(unittest.TestCase):
    def test_bridge_closed_form_summaries_and_integer_information(self):
        document = compare_configurations(ring_study())
        self.assertEqual(document["status"], "COMPLETE")
        actual = rows(document)
        expected = {
            "none": (2, 2, 5 / 16),
            "x": (4, 1, 0),
            "2x": (4, 1, 0),
            "y": (2, 1, 5 / 16),
            "mixed": (4, 1, 0),
            "redundant": (4, 1, 0),
            "full": (None, 0, 0),
            "xy": (None, 0, 0),
        }
        for key, values in expected.items():
            with self.subTest(configuration=key):
                self.assertEqual(
                    tuple(
                        actual[key][field]
                        for field in (
                            "first_hidden_layer",
                            "computed_hidden_rank",
                            "entropy_log_t_coefficient",
                        )
                    ),
                    values,
                )
        self.assertEqual(relation(document, "x", "2x")["relation"], "EQUIVALENT")
        self.assertEqual(
            relation(document, "mixed", "redundant")["relation"], "EQUIVALENT"
        )
        self.assertEqual(relation(document, "full", "xy")["relation"], "EQUIVALENT")
        self.assertEqual(
            relation(document, "none", "x")["relation"], "RIGHT_REFINES_LEFT"
        )
        self.assertEqual(relation(document, "x", "mixed")["relation"], "INCOMPARABLE")
        self.assertEqual(actual["redundant"]["redundant_channels"], ["z", "2z"])
        self.assertEqual(actual["full"]["redundant_channels"], [])
        self.assertEqual(actual["mixed"]["visible_torsion"], {"4": [2]})
        self.assertEqual(
            abs(
                int(
                    matrix(
                        document["results"]["full"]["homology"]["readout_matrix"]
                    ).det()
                )
            ),
            2,
        )

    def test_certificates_reconstruct_and_witnesses_distinguish_histories(self):
        document = compare_configurations(ring_study())
        for pair in document["relations"]:
            left = document["results"][pair["left"]]
            right = document["results"][pair["right"]]
            l_kernel = matrix(
                left["filtration"]["layers"][-1]["hidden"]["basis_columns"]
            )
            r_kernel = matrix(
                right["filtration"]["layers"][-1]["hidden"]["basis_columns"]
            )
            for key, sub, sup in (
                ("left_kernel_in_right", l_kernel, r_kernel),
                ("right_kernel_in_left", r_kernel, l_kernel),
            ):
                certificate = pair[key]
                if certificate["included"]:
                    self.assertEqual(sup * matrix(certificate["coordinates"]), sub)
            for key, invisible, visible in (
                ("left_not_right_witness", "left_readout", "right_readout"),
                ("right_not_left_witness", "right_readout", "left_readout"),
            ):
                witness = pair[key]
                if witness is None:
                    continue
                self.assertFalse(any(witness[invisible]))
                self.assertTrue(any(witness[visible]))
                chain = {
                    tuple(item["edge"]): item["coefficient"]
                    for item in witness["edge_chain"]
                }
                balance = dict.fromkeys(left["model"]["vertices"], 0)
                for (u, v), coefficient in chain.items():
                    balance[u] -= coefficient
                    balance[v] += coefficient
                self.assertTrue(all(value == 0 for value in balance.values()))
                for side, payload in (("left", left), ("right", right)):
                    measured = []
                    for readout in payload["model"]["readouts"]:
                        measured.append(
                            sum(
                                item["coefficient"] * chain.get(tuple(item["edge"]), 0)
                                for item in readout["coefficients"]
                            )
                        )
                    self.assertEqual(measured, witness[side + "_readout"])

    def test_tree_and_edge_orientation_do_not_change_information_relation(self):
        study = ring_study()
        first = compare_configurations(study)
        changed = copy.deepcopy(study)
        changed["model"]["edges"] = [
            edge[::-1] for edge in reversed(changed["model"]["edges"])
        ]
        for config in changed["configurations"]:
            for readout in config["readouts"]:
                for item in readout["coefficients"]:
                    item["edge"].reverse()
                    item["coefficient"] *= -1
        second = compare_configurations(changed, reverse_tree_order=True)
        self.assertEqual(
            [p["relation"] for p in first["relations"]],
            [p["relation"] for p in second["relations"]],
        )
        for left, right in zip(first["rows"], second["rows"]):
            for field in (
                "first_hidden_layer",
                "computed_hidden_rank",
                "entropy_log_t_coefficient",
                "visible_torsion",
                "redundant_channels",
            ):
                self.assertEqual(left[field], right[field])

    def test_theta_equal_objectives_do_not_decide_information(self):
        paths = [["s", "a", "t"], ["s", "b1", "b2", "t"], ["s", "c1", "c2", "c3", "t"]]
        study = ring_study()
        study["model"]["vertices"] = sorted({v for path in paths for v in path})
        study["model"]["edges"] = [
            list(edge) for path in paths for edge in zip(path, path[1:])
        ]
        x, y = ("s", "b1"), ("s", "c1")
        study["configurations"] = [
            {"id": "x", "readouts": [counter("x", [(x, -1)])]},
            {"id": "y", "readouts": [counter("y", [(y, -1)])]},
            {"id": "mixed", "readouts": [counter("x+y", [(x, -1), (y, -1)])]},
        ]
        document = compare_configurations(study)
        for row in document["rows"]:
            self.assertEqual(row["first_hidden_layer"], 3)
            self.assertEqual(row["computed_hidden_rank"], 1)
            self.assertEqual(row["entropy_log_t_coefficient"], 1 / 8)
        for pair in document["relations"]:
            self.assertEqual(pair["relation"], "INCOMPARABLE")
            self.assertEqual(pair["metric_comparison"]["first_hidden_layer"], "TIED")
            self.assertTrue(pair["metric_comparison"]["entropy_coefficient_tied"])

    def test_partial_scope_does_not_become_full_information(self):
        study = ring_study()
        study["analysis"]["max_layer"] = 3
        document = compare_configurations(study)
        self.assertEqual(document["status"], "INCOMPLETE")
        self.assertEqual(rows(document)["x"]["computed_hidden_rank"], 0)
        pair = relation(document, "x", "mixed")
        self.assertEqual(pair["relation"], "EQUIVALENT")
        self.assertEqual(pair["scope"], "COMPUTED_EXPOSURE")
        self.assertFalse(rows(document)["x"]["natural_complete"])

    def test_failed_candidate_and_cycle_limit_do_not_assert_relations(self):
        study = ring_study()
        study["configurations"][0]["readouts"] = [
            counter("bad", [(("unknown", "vertex"), 1)])
        ]
        document = compare_configurations(study)
        self.assertEqual(rows(document)["none"]["status"], "ERROR")
        self.assertEqual(rows(document)["x"]["status"], "COMPLETE")
        self.assertEqual(relation(document, "none", "x")["relation"], "UNAVAILABLE")
        study["analysis"]["max_cycles"] = 1
        document = compare_configurations(study)
        self.assertEqual(rows(document)["x"]["status"], "LIMIT_REACHED")
        self.assertIsNone(rows(document)["x"]["computed_hidden_rank"])
        self.assertTrue(
            all(p["relation"] == "UNAVAILABLE" for p in document["relations"])
        )

    def test_critical_and_near_critical_phases_are_preserved(self):
        study = ring_study()
        study["analysis"]["alpha"] = 1 / 3
        document = compare_configurations(study)
        phase = next(
            layer
            for layer in document["results"]["x"]["phase"]["layers"]
            if layer["layer"] == 4
        )
        self.assertEqual(phase["regime"], "DENSE")
        self.assertEqual(rows(document)["x"]["entropy_log_t_coefficient"], 2**-55)
        study = ring_study((3, 5), bridge=False)
        study["analysis"]["alpha"] = 0.5
        document = compare_configurations(study)
        phase = next(
            layer
            for layer in document["results"]["x"]["phase"]["layers"]
            if layer["layer"] == 3
        )
        self.assertEqual(phase["regime"], "CRITICAL")
        self.assertEqual(rows(document)["x"]["computed_hidden_rank"], 1)
        self.assertEqual(rows(document)["x"]["entropy_log_t_coefficient"], 0)

    def test_three_rings_retain_hidden_late_cycle(self):
        study = ring_study((3, 5, 9), bridge=False)
        document = compare_configurations(study)
        actual = rows(document)
        self.assertEqual(actual["none"]["entropy_log_t_coefficient"], 7 / 16)
        self.assertEqual(actual["x"]["entropy_log_t_coefficient"], 1 / 8)
        self.assertEqual(actual["xy"]["first_hidden_layer"], 5)
        self.assertEqual(actual["xy"]["computed_hidden_rank"], 1)
        self.assertEqual(actual["xy"]["entropy_log_t_coefficient"], 0)

    def test_zero_homology_and_zero_functional_are_valid(self):
        study = ring_study()
        study["model"] = {
            "schema_version": 1,
            "name": "tree",
            "vertices": ["u", "v"],
            "edges": [["u", "v"]],
        }
        study["configurations"] = [
            {"id": "none", "readouts": []},
            {"id": "edge", "readouts": [counter("edge", [(("u", "v"), 1)])]},
        ]
        document = compare_configurations(study)
        self.assertEqual(document["status"], "COMPLETE")
        self.assertEqual(document["relations"][0]["relation"], "EQUIVALENT")
        self.assertEqual(rows(document)["edge"]["redundant_channels"], ["edge"])

    def test_public_input_cannot_mutate_normalized_study(self):
        source = ring_study()
        parsed = parse_study(source)
        source["configurations"][1]["readouts"][0]["coefficients"][0]["coefficient"] = (
            99
        )
        self.assertEqual(
            parsed["configurations"][1]["readouts"][0]["coefficients"][0][
                "coefficient"
            ],
            1,
        )


if __name__ == "__main__":
    unittest.main()
