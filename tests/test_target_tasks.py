"""Independent algebra, finite-walk and public-contract target regressions."""

from __future__ import annotations

import contextlib
import copy
import io
import itertools
import json
import random
import tempfile
import unittest
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from unittest import mock

from jsonschema import Draft202012Validator
from sympy import Matrix

import homological_observability as ho
from homological_observability import cli
from homological_observability.homology import build_homology_basis
from homological_observability.integer_lattice import integer_kernel

ROOT = Path(__file__).resolve().parents[1]


def matrix(document):
    return Matrix(document["rows"], document["columns"], sum(document["data"], []))


def rational_rank(rows, width):
    """Independent Fraction elimination, without the product's SymPy rank."""
    rows = [[Fraction(v) for v in row] for row in rows]
    pivot = 0
    for column in range(width):
        found = next((i for i in range(pivot, len(rows)) if rows[i][column]), None)
        if found is None:
            continue
        rows[pivot], rows[found] = rows[found], rows[pivot]
        divisor = rows[pivot][column]
        rows[pivot] = [x / divisor for x in rows[pivot]]
        for i in range(pivot + 1, len(rows)):
            factor = rows[i][column]
            rows[i] = [x - factor * y for x, y in zip(rows[i], rows[pivot])]
        pivot += 1
        if pivot == len(rows):
            break
    return pivot


def lattice_model(p, f, width=None):
    width = width or len(f[0])
    vertices = ["o"] + [f"v{i}{j}" for i in range(width) for j in (0, 1)]
    edges = (
        [("o", f"v{i}0") for i in range(width)]
        + [(f"v{i}0", f"v{i}1") for i in range(width)]
        + [(f"v{i}1", "o") for i in range(width)]
    )
    model = ho.GraphModel.create(
        name="integer-image test", vertices=vertices, edges=edges
    )
    basis = build_homology_basis(model)

    def cochain(name, row):
        return ho.IntegerReadout.from_mapping(name, dict(zip(basis.chord_edges, row)))

    readouts = tuple(cochain(f"P{i}", row) for i, row in enumerate(p))
    return replace(model, readouts=readouts), tuple(
        cochain(f"F{i}", row) for i, row in enumerate(f)
    )


def dfr():
    request = json.loads((ROOT / "examples/dfr_design.json").read_text())
    model = ho.parse_model(request["model"])
    targets = ho.parse_model(
        {**request["model"], "readouts": request["targets"]}
    ).readouts
    pool = ho.parse_model(
        {**request["model"], "readouts": request["candidates"]}
    ).readouts
    return model, targets, pool


def path_value(walk, readout):
    values = readout.as_mapping()
    return sum(
        values.get((u, v), 0) - values.get((v, u), 0) for u, v in zip(walk, walk[1:])
    )


class TargetAlgebraTests(unittest.TestCase):
    def test_random_integer_maps_against_independent_rank_and_preimages(self):
        rng = random.Random(621108)
        for _ in range(80):
            width = rng.randrange(1, 5)
            p = [
                [rng.randrange(-3, 4) for _ in range(width)]
                for _ in range(rng.randrange(5))
            ]
            f = [
                [rng.randrange(-2, 3) for _ in range(width)]
                for _ in range(rng.randrange(1, 4))
            ]
            model, targets = lattice_model(p, f)
            expected = rational_rank(p, width) == rational_rank(p + f, width)
            document = ho.analyze_target(model, targets)
            self.assertEqual(document["result"]["sufficient"], expected)
            z = [rng.randrange(-5, 6) for _ in range(width)]
            values = {
                f"P{i}": sum(a * b for a, b in zip(row, z)) for i, row in enumerate(p)
            }
            decoded = ho.evaluate_target(model, targets, values, record_kind="cycle")[
                "result"
            ]
            self.assertTrue(decoded["legal_record"])
            if expected:
                self.assertEqual(
                    decoded["target_values"],
                    {
                        f"F{i}": sum(a * b for a, b in zip(row, z))
                        for i, row in enumerate(f)
                    },
                )
            else:
                self.assertIsNone(decoded["target_values"])
                certificate = document["result"]["certificate"]
                witness = matrix(certificate["cycle_coordinates"])
                self.assertFalse(any(matrix(document["basis"]["readouts"]) * witness))
                self.assertTrue(any(matrix(document["basis"]["targets"]) * witness))

    def test_dfr_witness_and_two_minimum_augmentations(self):
        model, targets, pool = dfr()
        document = ho.analyze_target(model, targets)
        self.assertFalse(document["result"]["sufficient"])
        certificate = document["result"]["certificate"]
        z = matrix(certificate["cycle_coordinates"])
        self.assertEqual(matrix(document["basis"]["readouts"]) * z, Matrix.zeros(1, 1))
        self.assertEqual(abs(int(matrix(certificate["target_change"])[0])), 2)
        edge_chain = matrix(certificate["edge_chain"])
        self.assertEqual(matrix(document["basis"]["cycles"]) * z, edge_chain)
        boundary = dict.fromkeys(model.vertices, 0)
        for (u, v), count in zip(model.edges, edge_chain):
            boundary[u] -= count
            boundary[v] += count
        self.assertTrue(all(v == 0 for v in boundary.values()))
        design = ho.design_readouts(model, targets, pool)["result"]
        self.assertEqual(design["minimum_added"], 1)
        self.assertEqual((design["fixed_count"], design["minimum_total"]), (1, 2))
        self.assertEqual(
            (design["lower_bound_added"], design["upper_bound_added"]), (1, 1)
        )
        self.assertTrue(design["minimum_proven"] and design["ties_complete"])
        self.assertEqual(
            [s["added_ids"] for s in design["solutions"]], [["W_ON"], ["W_OFF"]]
        )
        self.assertEqual(
            [s["certificate"]["decoder"]["data"] for s in design["solutions"]],
            [[["-1", "2"]], [["1", "-2"]]],
        )

    def test_dfr_from_zero_full_history_and_weighted_switch_targets(self):
        model, targets, pool = dfr()
        pool = (*model.readouts, *pool)
        model = replace(model, readouts=())
        basis = build_homology_basis(model)
        full = tuple(
            ho.IntegerReadout.from_mapping(f"h{i}", {edge: 1})
            for i, edge in enumerate(basis.chord_edges)
        )
        switch = (
            ho.IntegerReadout.from_mapping("switch", {("0", "3"): 2, ("1", "4"): 1}),
        )
        for target, minimum, ties in [(targets, 2, 3), (full, 4, 9), (switch, 2, 3)]:
            result = ho.design_readouts(model, target, pool)["result"]
            self.assertEqual(
                (result["minimum_added"], result["ties_found"]), (minimum, ties)
            )
            self.assertTrue(result["ties_complete"])

    def test_all_dfr_subsets_against_fraction_rank(self):
        model, targets, pool = dfr()
        pool = (*model.readouts, *pool)
        for size in range(len(pool) + 1):
            for subset in itertools.combinations(pool, size):
                document = ho.analyze_target(replace(model, readouts=subset), targets)
                p = document["basis"]["readouts"]["data"]
                f = document["basis"]["targets"]["data"]
                expected = rational_rank(p, 4) == rational_rank(p + f, 4)
                self.assertEqual(document["result"]["sufficient"], expected)
                if expected:
                    decoder = matrix(document["result"]["certificate"]["decoder"])
                    self.assertEqual(
                        decoder * matrix(document["basis"]["readouts"]),
                        matrix(document["basis"]["targets"]),
                    )

    def test_already_sufficient_empty_pool_and_infeasible_pool(self):
        model, targets, pool = dfr()
        sufficient = replace(model, readouts=(*model.readouts, pool[0]))
        result = ho.design_readouts(sufficient, targets, ())["result"]
        self.assertEqual(result["minimum_added"], 0)
        self.assertEqual(result["solutions"][0]["added_ids"], [])
        for candidates in ((), pool[2:]):
            result = ho.design_readouts(model, targets, candidates)["result"]
            self.assertFalse(result["feasible"])
            self.assertIsNone(result["minimum_added"])
            self.assertFalse(result["minimum_proven"])
            self.assertEqual(result["subsets_examined"], 0)

    def test_distinct_physical_channels_and_more_than_64_candidates(self):
        model, target = lattice_model([], [[1]])
        pool = tuple(replace(target[0], name=f"device{i}") for i in range(65))
        result = ho.design_readouts(model, target, pool)["result"]
        self.assertEqual(result["minimum_added"], 1)
        self.assertEqual(len(result["solutions"]), 65)
        self.assertTrue(result["ties_complete"])

    def test_search_proves_global_minimum_not_deletion_minimality(self):
        model, target = lattice_model([], [[1, 0]])
        basis = build_homology_basis(model)
        pool = tuple(
            ho.IntegerReadout.from_mapping(name, dict(zip(basis.chord_edges, row)))
            for name, row in [("x+y", [1, 1]), ("y", [0, 1]), ("x", [1, 0])]
        )
        result = ho.design_readouts(model, target, pool)["result"]
        self.assertEqual([s["added_ids"] for s in result["solutions"]], [["x"]])

    def test_rational_decoder_only_on_legal_image(self):
        model, targets = lattice_model([[2]], [[1]])
        self.assertEqual(
            ho.analyze_target(model, targets)["result"]["certificate"]["decoder"][
                "data"
            ],
            [["1/2"]],
        )
        for value, legal, expected in [(6, True, {"F0": 3}), (3, False, None)]:
            result = ho.evaluate_target(
                model, targets, {"P0": value}, record_kind="cycle"
            )["result"]
            self.assertEqual(
                (result["legal_record"], result["target_values"]), (legal, expected)
            )

    def test_every_legal_image_constraint_is_checked(self):
        for p, f, values in [
            ([[2, 0], [0, 2]], [[1, 1]], {"P0": 1, "P1": 1}),
            ([[2], [4]], [[1]], {"P0": 2, "P1": 5}),
        ]:
            model, targets = lattice_model(p, f)
            result = ho.evaluate_target(model, targets, values, record_kind="cycle")[
                "result"
            ]
            self.assertTrue(result["sufficient"])
            self.assertFalse(result["legal_record"])
            self.assertIsNone(result["target_values"])

    def test_saturated_kernel_not_columnwise_denominator_clearing(self):
        p = Matrix([[2, 1, 1]])
        kernel = integer_kernel(p)
        image = Matrix([[0, 1, 0]]) * kernel
        from math import gcd

        self.assertEqual(gcd(*[int(x) for x in image]), 1)
        model, targets = lattice_model([[2, 1, 1]], [[0, 1, 0]])
        result = ho.evaluate_target(model, targets, {"P0": 1}, record_kind="cycle")[
            "result"
        ]
        self.assertTrue(result["legal_record"])
        self.assertFalse(result["sufficient"])
        self.assertIsNone(result["target_values"])

    def test_tree_pure_gradient_zero_and_single_vertex(self):
        for vertices, edges, coeff, start, end, expected in [
            (["a", "b"], [("a", "b")], {("a", "b"): 3}, "a", "b", 3),
            (["a"], [], {}, "a", "a", 0),
        ]:
            model = ho.GraphModel.create(
                name="endpoint", vertices=vertices, edges=edges
            )
            target = (ho.IntegerReadout.from_mapping("endpoint", coeff),)
            self.assertTrue(ho.analyze_target(model, target)["result"]["sufficient"])
            self.assertEqual(
                ho.design_readouts(model, target, ())["result"]["minimum_added"], 0
            )
            result = ho.evaluate_target(model, target, {}, start=start, end=end)[
                "result"
            ]
            self.assertEqual(result["target_values"], {"endpoint": expected})

    def test_endpoint_corrections_and_spanning_tree_independence(self):
        model, targets, pool = dfr()
        target_gradient = ho.IntegerReadout.from_mapping(
            "endpoint", {(u, v): int(v) - int(u) for u, v in model.edges}
        )
        targets = (*targets, target_gradient)
        adjacency = {v: [] for v in model.vertices}
        for u, v in model.edges:
            adjacency[u].append(v)
            adjacency[v].append(u)
        rng = random.Random(20261108)
        for _ in range(40):
            walk = [rng.choice(model.vertices)]
            for _ in range(rng.randrange(30)):
                walk.append(rng.choice(adjacency[walk[-1]]))
            expected = {r.name: path_value(walk, r) for r in targets}
            for channel in pool[:2]:
                scheme = replace(model, readouts=(*model.readouts, channel))
                values = {r.name: path_value(walk, r) for r in scheme.readouts}
                for reverse in (False, True):
                    document = ho.evaluate_target(
                        scheme,
                        targets,
                        values,
                        start=walk[0],
                        end=walk[-1],
                        reverse_tree_order=reverse,
                    )
                    self.assertEqual(document["result"]["target_values"], expected)
                    cycle = ho.evaluate_target(
                        scheme,
                        targets,
                        document["result"]["corrected_record"],
                        record_kind="cycle",
                        reverse_tree_order=reverse,
                    )
                    self.assertEqual(
                        {
                            k: cycle["result"]["target_values"][k]
                            + document["result"]["endpoint_targets"][k]
                            for k in expected
                        },
                        expected,
                    )

    def test_cycle_filtration_limits_do_not_limit_target_task(self):
        model, targets, pool = dfr()
        model = replace(model, max_cycles=1, max_layer=1)
        with mock.patch(
            "homological_observability.analysis.analyze_model",
            side_effect=AssertionError("unexpected filtration"),
        ):
            self.assertEqual(ho.analyze_target(model, targets)["status"], "COMPLETE")
            self.assertTrue(
                ho.design_readouts(model, targets, pool)["result"]["ties_complete"]
            )


class TargetBoundaryTests(unittest.TestCase):
    def test_search_limit_after_first_solution_preserves_minimum(self):
        model, target, pool = dfr()
        result = ho.design_readouts(
            model, target, pool, limits=ho.TargetLimits(max_subsets=1)
        )
        self.assertEqual(result["status"], "LIMIT_REACHED")
        self.assertTrue(result["result"]["minimum_proven"])
        self.assertFalse(result["result"]["ties_complete"])
        self.assertTrue(result["result"]["certificates_complete"])
        self.assertEqual(result["result"]["minimum_added"], 1)

    def test_search_limit_before_first_solution_does_not_claim_minimum(self):
        model, target, pool = dfr()
        result = ho.design_readouts(
            model, target, (*pool[2:], *pool[:2]), limits=ho.TargetLimits(max_subsets=1)
        )["result"]
        self.assertTrue(result["feasible"])
        self.assertFalse(result["minimum_proven"])
        self.assertIsNone(result["minimum_added"])
        self.assertEqual(result["lower_bound_added"], 1)
        self.assertEqual(result["upper_bound_added"], len(pool))

    def test_output_truncation_does_not_erase_enumeration(self):
        model, target, pool = dfr()
        document = ho.design_readouts(
            model, target, pool, limits=ho.TargetLimits(max_solutions=1)
        )
        result = document["result"]
        self.assertTrue(result["minimum_proven"] and result["enumeration_complete"])
        self.assertEqual(result["ties_found"], 2)
        self.assertTrue(result["output_truncated"])
        self.assertFalse(result["ties_complete"])
        self.assertEqual(len(result["solutions"]), 1)
        self.assertEqual(document["status"], "LIMIT_REACHED")

    def test_certificate_integer_budget_preserves_rank_decision(self):
        model, target = lattice_model([[2, 1, 0], [0, 2, 1], [0, 0, 2]], [[1, 0, 0]])
        document = ho.analyze_target(
            model, target, limits=ho.TargetLimits(max_integer_bits=2)
        )
        self.assertTrue(document["result"]["sufficient"])
        self.assertEqual(
            document["limit"], {"stage": "certificate", "resource": "integer_bits"}
        )
        self.assertFalse(document["result"]["certificate_complete"])

    def test_prechecks_have_memory_bit_and_time_budgets(self):
        model, target = lattice_model([[2]], [[1]])
        for limits, resource in [
            (ho.TargetLimits(max_matrix_entries=1), "matrix_entries"),
            (ho.TargetLimits(max_integer_bits=1), "integer_bits"),
        ]:
            document = ho.analyze_target(model, target, limits=limits)
            self.assertIsNone(document["result"]["sufficient"])
            self.assertEqual(document["limit"]["resource"], resource)
        # The Windows monotonic clock can return the same reading during this
        # tiny calculation. Test elapsed-time behavior with a controlled clock.
        with mock.patch(
            "homological_observability._target_common.time.monotonic",
            side_effect=itertools.count(0, 2),
        ):
            document = ho.analyze_target(
                model, target, limits=ho.TargetLimits(max_seconds=1)
            )
        self.assertIsNone(document["result"]["sufficient"])
        self.assertEqual(document["limit"]["resource"], "cooperative_seconds")

    def test_bad_cochains_candidates_records_and_limits(self):
        model, targets, pool = dfr()
        bad = ho.IntegerReadout.from_mapping("outside", {("absent", "0"): 1})
        for call in [
            lambda: ho.analyze_target(model, [bad]),
            lambda: ho.analyze_target(model, []),
            lambda: ho.design_readouts(model, targets, [bad]),
            lambda: ho.design_readouts(model, targets, [pool[0], pool[0]]),
            lambda: ho.design_readouts(model, targets, model.readouts),
            lambda: ho.evaluate_target(model, targets, {"W": True}, start="0", end="3"),
            lambda: ho.evaluate_target(model, targets, {"W": 0}),
            lambda: ho.evaluate_target(
                model, targets, {"W": 0, "extra": 0}, start="0", end="3"
            ),
            lambda: ho.evaluate_target(
                model, targets, {"W": 0}, record_kind="cycle", start="0"
            ),
            lambda: ho.TargetLimits(max_seconds=float("nan")),
            lambda: ho.TargetLimits(max_subsets=True),
        ]:
            with self.assertRaises((TypeError, ValueError)):
                call()


class TargetContractTests(unittest.TestCase):
    def test_schemas_cover_complete_and_each_partial_state(self):
        request_validator = Draft202012Validator(ho.load_target_request_schema())
        validator = Draft202012Validator(ho.load_target_task_schema())
        request_validator.check_schema(request_validator.schema)
        validator.check_schema(validator.schema)
        model, targets, pool = dfr()
        documents = [
            ho.analyze_target(model, targets),
            ho.design_readouts(model, targets, pool),
            ho.design_readouts(model, targets, ()),
            ho.evaluate_target(model, targets, {"W": 0}, start="0", end="3"),
        ]
        for limits in [
            ho.TargetLimits(max_subsets=1),
            ho.TargetLimits(max_solutions=1),
            ho.TargetLimits(max_matrix_entries=1),
        ]:
            documents.append(ho.design_readouts(model, targets, pool, limits=limits))
        with mock.patch(
            "homological_observability._target_common.time.monotonic",
            side_effect=itertools.count(0, 2),
        ):
            documents.append(
                ho.design_readouts(
                    model, targets, pool, limits=ho.TargetLimits(max_seconds=1)
                )
            )
        for document in documents:
            request_validator.validate(document["request"])
            validator.validate(document)
            if document["status"] == "LIMIT_REACHED":
                falsely_complete = copy.deepcopy(document)
                falsely_complete["status"] = "COMPLETE"
                falsely_complete["limit"] = None
                self.assertFalse(validator.is_valid(falsely_complete))

    def test_examples_replay_and_cli_bundles(self):
        for name, command in [
            ("dfr_target", "target"),
            ("dfr_design", "design"),
            ("dfr_evaluate", "target"),
        ]:
            request = ho.load_target_request(ROOT / "examples" / f"{name}.json")
            document = ho.run_target_request(request)
            self.assertEqual(document, ho.run_target_request(document["request"]))
            with tempfile.TemporaryDirectory() as temp:
                output = Path(temp) / "bundle"
                stream = io.StringIO()
                with contextlib.redirect_stdout(stream):
                    code = cli.main(
                        [
                            command,
                            str(ROOT / "examples" / f"{name}.json"),
                            "--format",
                            "json",
                            "--output-dir",
                            str(output),
                        ]
                    )
                self.assertEqual(code, 0)
                self.assertEqual(json.loads(stream.getvalue()), document)
                self.assertEqual(
                    ho.run_target_request(
                        ho.load_target_request(output / "request.json")
                    ),
                    document,
                )
                self.assertEqual(
                    json.loads((output / "result.json").read_text()), document
                )
                with self.assertRaises(FileExistsError):
                    ho.write_target_bundle(document, output)

    def test_version_mismatch_unknown_fields_and_command_mismatch(self):
        request = ho.load_target_request(ROOT / "examples/dfr_design.json")
        for update in [
            {"schema_version": 2},
            {"unknown": 1},
            {"reverse_tree_order": 1},
            {"limits": {"unknown": 1}},
            {"record": {"kind": "cycle", "values": {}}},
        ]:
            with self.assertRaises((TypeError, ValueError)):
                ho.run_target_request({**request, **update})
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            code = cli.main(
                ["target", str(ROOT / "examples/dfr_design.json"), "--format", "json"]
            )
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(stream.getvalue())["status"], "ERROR")


class TargetReportTests(unittest.TestCase):
    def test_unfinished_decision_is_distinct_from_insufficiency(self):
        model, targets, pool = dfr()
        diagnosis = ho.analyze_target(model, targets)
        text = ho.render_target_text(diagnosis)
        self.assertIn("do not determine every target", text)
        self.assertIn("DeltaW changes by 2", text)
        limited = ho.analyze_target(
            model, targets, limits=ho.TargetLimits(max_matrix_entries=1)
        )
        text = ho.render_target_text(limited)
        self.assertIn("sufficiency has not been established", text)
        self.assertNotIn("do not determine", text)
        for document in (
            limited,
            ho.design_readouts(
                model, targets, pool, limits=ho.TargetLimits(max_matrix_entries=1)
            ),
        ):
            text = ho.render_target_text(document)
            self.assertIn("LIMIT_REACHED", text)
            self.assertNotIn("None", text)
            self.assertNotIn("cannot determine", text)

    def test_illegal_record_has_no_decoded_value_and_cycle_value_is_labeled(self):
        model, targets = lattice_model([[2]], [[1]])
        illegal = ho.evaluate_target(model, targets, {"P0": 1}, record_kind="cycle")
        text = ho.render_target_text(illegal)
        self.assertIn("outside the legal integer image", text)
        self.assertNotIn("F0 =", text)
        legal = ho.evaluate_target(model, targets, {"P0": 2}, record_kind="cycle")
        text = ho.render_target_text(legal)
        self.assertIn("Cycle target values", text)
        self.assertIn("F0 = 1", text)
        self.assertNotIn("Raw target values", text)

    def test_finite_scale_and_zero_entropy_are_not_missing_values(self):
        model, targets, _ = dfr()
        finite = ho.analyze_target(
            replace(model, observation_time=2.5, sampling_interval=0.05),
            targets,
            explain=True,
        )
        text = ho.render_target_text(finite)
        self.assertIn("exposure scale approximately 0.125", text)
        self.assertNotIn("entropy log(T) coefficient", text)
        self.assertNotIn("None", text)
        sparse = ho.analyze_target(replace(model, alpha=2), targets, explain=True)
        self.assertIn(
            "Target entropy log(T) coefficient: 0", ho.render_target_text(sparse)
        )
        # A zero asymptotic coefficient must not turn insufficiency into recovery.
        self.assertIn("do not determine every target", ho.render_target_text(sparse))


if __name__ == "__main__":
    unittest.main()
