"""Independent path-space and analytic checks of finite-record inference."""

import copy
import math
import unittest
from collections import defaultdict
from itertools import combinations

from jsonschema import Draft202012Validator
from scipy.special import iv

import homological_observability as ho
from homological_observability.record_io import recording_example


def uniformization_reference(request, jump_limit):
    """Positive recursion on physical edge currents, with no homology basis or FFT."""
    model = request["model"]
    record = request["record"]
    rates = {(r["from"], r["to"]): r["rate"] for r in request["rates"]}
    exits = {
        v: sum(val for (u, _), val in rates.items() if u == v)
        for v in model["vertices"]
    }
    rate = max(exits.values())
    rules = [
        {tuple(x["edge"]): x["coefficient"] for x in rule["coefficients"]}
        for rule in [request["target"], *model["readouts"]]
    ]
    zero = (0,) * len(rules)
    distribution = {zero: 1.0}
    for j, (start, end) in enumerate(zip(record["states"], record["states"][1:])):
        mean = rate * (record["times"][j + 1] - record["times"][j])
        poisson = math.exp(-mean)
        active = {(start, zero): 1.0}
        window = defaultdict(float)
        for level in range(jump_limit + 1):
            for (u, z), p in active.items():
                if u == end:
                    window[z] += p * poisson
            if level == jump_limit:
                break
            nxt = defaultdict(float)
            for (u, z), p in active.items():
                stay = 1 - exits[u] / rate
                if stay > 0:
                    nxt[u, z] += p * stay
                for (v, w), r in rates.items():
                    if u == v:
                        coord = tuple(
                            k + rule.get((v, w), 0) - rule.get((w, v), 0)
                            for k, rule in zip(z, rules)
                        )
                        nxt[w, coord] += p * r / rate
            active = nxt
            poisson *= mean / (level + 1)
        merged = defaultdict(float)
        for z, p in distribution.items():
            for k, q in window.items():
                merged[tuple(a + b for a, b in zip(z, k))] += p * q
        distribution = merged
    observed = tuple(record["counts"][rule["name"]] for rule in model["readouts"])
    mass = {z[0]: p for z, p in distribution.items() if z[1:] == observed}
    total = math.fsum(mass.values())
    return {z: p / total for z, p in mass.items()}, total


def output(request):
    return ho.infer_target_posterior(request)["result"]


class PosteriorTests(unittest.TestCase):
    def setUp(self):
        self.triangle = recording_example("posterior", "triangle")

    def test_entire_triangle_distribution_and_named_probability(self):
        req = self.triangle
        req["target_sets"] = [{"name": "nonpositive", "max": 0}]
        r = output(req)
        pmf = {row["value"]: row["probability"] for row in r["pmf"]}
        expected = {z: float(iv(3 * abs(z), 2)) for z in range(-20, 21)}
        norm = sum(expected.values())
        self.assertLess(
            sum(abs(p / norm - pmf.get(z, 0)) for z, p in expected.items()), 2e-12
        )
        self.assertEqual(r["map_candidates"], [0])
        self.assertAlmostEqual(r["map_risk"], 0.15828779821195978, places=13)
        self.assertAlmostEqual(
            r["set_probabilities"]["nonpositive"], (1 + pmf[0]) / 2, places=13
        )

    def test_positive_reference_open_path_and_whole_record_conditioning(self):
        req = recording_example("posterior", "dfr")
        req["record"] = {
            "states": ["0", "1", "4"],
            "times": [0, 0.15, 0.30],
            "counts": {"W": 0},
        }
        req["reverse_tree_order"] = True
        ref, evidence = uniformization_reference(req, 20)
        r = output(req)
        self.assertEqual(r["outcome"], "NUMERICAL_POSTERIOR")
        self.assertTrue(all(row["value"] % 2 == 0 for row in r["pmf"]))
        got = {row["value"]: row["probability"] for row in r["pmf"]}
        self.assertLess(
            sum(abs(got.get(z, 0) - ref.get(z, 0)) for z in got.keys() | ref.keys()),
            1e-10,
        )
        self.assertAlmostEqual(
            math.exp(r["diagnostics"]["log_record_probability"]), evidence, places=12
        )
        req["reverse_tree_order"] = False
        renamed = {
            v: "label " + str(len(req["model"]["vertices"]) - i)
            for i, v in enumerate(req["model"]["vertices"])
        }
        model = req["model"]
        model["vertices"] = [renamed[v] for v in model["vertices"][::-1]]
        model["edges"] = [[renamed[v], renamed[u]] for u, v in model["edges"]]
        for cochain in [*model["readouts"], req["target"]]:
            for term in cochain["coefficients"]:
                u, v = term["edge"]
                term["edge"] = [renamed[v], renamed[u]]
                term["coefficient"] *= -1
        for edge in req["rates"]:
            edge["from"], edge["to"] = renamed[edge["from"]], renamed[edge["to"]]
        req["rates"].reverse()
        req["record"]["states"] = [renamed[v] for v in req["record"]["states"]]
        self.assertAlmostEqual(output(req)["map_risk"], r["map_risk"], places=11)

    def test_doubled_count_exact_illegal_and_structural_first(self):
        req = self.triangle
        counter = copy.deepcopy(req["target"])
        counter["name"] = "twice"
        counter["coefficients"][0]["coefficient"] = 2
        req["model"]["readouts"] = [counter]
        req["record"]["counts"] = {"twice": 6}
        req["limits"] = {"max_grid_points": 1, "max_matrix_entries": 1}
        r = output(req)
        self.assertEqual((r["map_candidates"], r["map_risk"]), ([3], 0.0))
        req.pop("rates")
        req["record"]["counts"]["twice"] = 5
        r = output(req)
        self.assertFalse(r["legal_record"])
        self.assertEqual(r["failed_count_constraint"]["modulus"], 2)
        self.assertIsNone(r["pmf"])
        req["record"] = {"times": [0], "states": ["a"], "counts": {"twice": 6}}
        self.assertEqual(
            output(req)["diagnostics"]["reason"], "nonzero_count_at_zero_duration"
        )
        req["record"]["counts"]["twice"] = 0
        self.assertEqual(output(req)["map_candidates"], [0])

    def test_c4_diametric_tie_and_open_gradient(self):
        req = self.triangle
        model = req["model"]
        model.update(
            vertices=["a", "b", "c", "d"],
            edges=[["a", "b"], ["b", "c"], ["c", "d"], ["d", "a"]],
        )
        req["rates"] = [
            {"from": u, "to": v, "rate": 1}
            for a, b in model["edges"]
            for u, v in ((a, b), (b, a))
        ]
        req["target"]["coefficients"] = [{"edge": ["d", "a"], "coefficient": 1}]
        req["record"].update(states=["a", "c"], times=[0, 1])
        self.assertEqual(output(req)["map_candidates"], [-1, 0])
        req.pop("rates")
        req["target"]["coefficients"] = [
            {"edge": ["c", "b"], "coefficient": 1},
            {"edge": ["c", "d"], "coefficient": 1},
        ]
        self.assertEqual(output(req)["map_candidates"], [-1])

    def test_rank_limit_and_exact_target_at_large_joint_rank(self):
        r = self.triangle
        m = r["model"]
        m["vertices"] = list("abcde")
        m["edges"] = [list(e) for e in combinations("abcde", 2)]
        m["readouts"] = [
            {"name": a + b, "coefficients": [{"edge": [a, b], "coefficient": 1}]}
            for a, b in (("b", "c"), ("b", "d"), ("b", "e"))
        ]
        r["record"]["counts"] = {c["name"]: 0 for c in m["readouts"]}
        r.pop("rates")
        r["target"] = dict(m["readouts"][0], name="target")
        self.assertEqual(output(r)["map_candidates"], [0])
        r["target"] = {
            "name": "target",
            "coefficients": [{"edge": ["c", "e"], "coefficient": 1}],
        }
        d = ho.infer_target_posterior(r)
        self.assertEqual(d["status"], "UNSUPPORTED_RANK")
        self.assertTrue(d["result"]["legal_record"])

    def test_unresolved_and_input_errors(self):
        req = self.triangle
        small = {**req, "limits": {"max_grid_points": 4}}
        doc = ho.infer_target_posterior(small)
        self.assertEqual(doc["status"], "LIMIT_REACHED")
        self.assertTrue(doc["result"]["legal_record"])
        no_rates = dict(req)
        del no_rates["rates"]
        self.assertEqual(
            ho.infer_target_posterior(no_rates)["status"], "RATES_REQUIRED"
        )
        rare = recording_example("posterior", "dfr")
        rare["record"]["counts"]["W"] = 123457
        r = output(rare)
        self.assertTrue(r["legal_record"])
        self.assertIsNone(r["pmf"])
        for record in (
            {"times": [0, 2, 3], "states": ["a"] * 3, "counts": {}},
            {"times": [0, 1], "states": ["a", "missing"], "counts": {}},
            {"times": [0, 1], "states": ["a", "a"], "counts": {"undeclared": 1}},
        ):
            with self.assertRaises((ValueError, TypeError)):
                output({**req, "record": record})
        with self.assertRaises(ValueError):
            output({**req, "rates": req["rates"][:-1]})

    def test_wedge_integer_layers_and_regular_multibridge(self):
        req = self.triangle
        edges = [list(e) for e in ("ab", "bc", "ca", "ad", "de", "ef", "fg", "ga")]
        req["model"].update(vertices=list("abcdefg"), edges=edges, readouts=[])
        req["target"]["coefficients"] = [
            {"edge": list(edge), "coefficient": 1} for edge in ("ca", "ga")
        ]
        req["rates"] = [
            {"from": u, "to": v, "rate": 1}
            for a, b in edges
            for u, v in ((a, b), (b, a))
        ]
        req["record"] = {
            "states": ["a", "b", "g"],
            "times": [0, 0.12, 0.24],
            "counts": {},
        }
        reference, probability = uniformization_reference(req, 18)
        result = output(req)
        got = {r["value"]: r["probability"] for r in result["pmf"]}
        self.assertAlmostEqual(
            math.exp(result["diagnostics"]["log_record_probability"]),
            probability,
            places=12,
        )
        self.assertLess(
            sum(
                abs(got.get(z, 0) - reference.get(z, 0))
                for z in got.keys() | reference.keys()
            ),
            1e-10,
        )

    def test_kinesin_endpoint_correction_and_odd_support(self):
        req = recording_example("posterior", "kinesin")
        self.assertEqual(output(req)["map_candidates"], [1])
        req["model"]["readouts"].pop()
        del req["record"]["counts"]["A"]
        result = output(req)
        self.assertEqual(result["target_support"], {"offset": 1, "step": 2})

    def test_schema_and_replay_do_not_depend_on_input_order(self):
        req = self.triangle
        doc = ho.infer_target_posterior(req)
        Draft202012Validator(ho.load_posterior_request_schema()).validate(req)
        Draft202012Validator(ho.load_posterior_schema()).validate(doc)
        self.assertEqual(ho.infer_target_posterior(doc["request"]), doc)
        req["rates"].reverse()
        self.assertEqual(ho.infer_target_posterior(req), doc)
        invalid = copy.deepcopy(doc)
        invalid["result"]["outcome"] = "UNRESOLVED"
        self.assertFalse(
            Draft202012Validator(ho.load_posterior_schema()).is_valid(invalid)
        )


class ProtocolTests(unittest.TestCase):
    def test_dfr_sample_membership_risk_and_resource_comparison(self):
        req = recording_example("compare-protocols", "dfr")
        d = ho.compare_recording_protocols(req)
        r = d["result"]
        rows = r["protocols"]
        self.assertEqual(d["status"], "COMPLETE")
        self.assertEqual([x["resolved"] for x in rows], [64, 64, 64])
        self.assertAlmostEqual(rows[0]["mean_risk"], 0.399526, places=5)
        self.assertAlmostEqual(rows[1]["mean_risk"], 0.154173, places=5)
        self.assertEqual(rows[2]["mean_risk"], 0.0)
        self.assertEqual(len(set(r["trajectory_ids"])), 64)
        self.assertTrue(
            all(row["expected_difference_interval_95"] is None for row in rows)
        )
        self.assertTrue(rows[0]["mean_encoded_bytes"] < rows[1]["mean_encoded_bytes"])
        self.assertAlmostEqual(
            rows[1]["mean_risk_difference"],
            rows[1]["mean_risk"] - rows[0]["mean_risk"],
            places=12,
        )
        Draft202012Validator(ho.load_protocol_request_schema()).validate(req)
        Draft202012Validator(ho.load_protocol_comparison_schema()).validate(d)

    def test_simulated_study_preserves_trajectories_after_extreme_change_of_unit(self):
        request = recording_example("compare-protocols", "triangle")
        # Use a single bidirectional edge with a known target, so the test
        # isolates trajectory generation from Fourier arithmetic.
        request["model"].update(
            vertices=["a", "b"],
            edges=[["a", "b"]],
            readouts=[
                {
                    "name": "turn_counter",
                    "coefficients": [{"edge": ["a", "b"], "coefficient": 1}],
                }
            ],
        )
        request["target"] = dict(request["model"]["readouts"][0], name="step")
        request["source"].update(
            initial_distribution={"a": 1, "b": 0}, trajectories=128, seed=77
        )
        request["rates"] = [
            {"from": a, "to": b, "rate": 1.0} for a, b in (("a", "b"), ("b", "a"))
        ]
        request["horizon"] = 0.1
        reference = ho.compare_recording_protocols(request)["result"]["rows"]
        request["horizon"] = 1e308
        for edge in request["rates"]:
            edge["rate"] = 1e-309
        scaled = ho.compare_recording_protocols(request)["result"]["rows"]
        self.assertTrue(any(r["observation"]["states"][-1] == "b" for r in reference))
        self.assertEqual(
            [r["observation"] for r in scaled], [r["observation"] for r in reference]
        )

    def test_seeded_replay_unresolved_rows_and_invalid_paths(self):
        req = recording_example("compare-protocols", "triangle")
        req["limits"] = {"max_grid_points": 2}
        req["source"]["trajectories"] = 3
        d = ho.compare_recording_protocols(req)
        r = d["result"]
        self.assertEqual(ho.compare_recording_protocols(d["request"]), d)
        self.assertEqual(d["status"], "PARTIAL")
        self.assertEqual(len(r["rows"]), 6)
        p0, p1 = r["protocols"]
        self.assertEqual(p0["mean_risk_bounds"], [0, 1])
        self.assertEqual(p1["paired_difference_bounds"], [-1, 0])
        self.assertEqual(p1["mean_risk"], 0)
        self.assertIsNotNone(p1["expected_difference_interval_95"])
        event = {"trajectory_id": "a", "states": ["a"], "times": [0]}
        req["source"] = {
            "kind": "events",
            "name": "user",
            "trajectories": [event, event],
        }
        with self.assertRaisesRegex(ValueError, "duplicate"):
            ho.compare_recording_protocols(req)
        req["source"]["trajectories"] = [
            dict(event, states=["a", "a"], times=[0, 0.125])
        ]
        with self.assertRaisesRegex(ValueError, "outside"):
            ho.compare_recording_protocols(req)
