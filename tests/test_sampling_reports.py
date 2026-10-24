"""Reading surfaces reflect the request and retain incomplete-result boundaries."""

import copy
import re
import unittest
from unittest import mock

import homological_observability as ho


def readable(text):
    return re.sub(r"\\([^\w\s])", r"\1", text)


class SamplingReportTests(unittest.TestCase):
    def test_three_requests_use_computed_values_on_all_surfaces(self):
        for settings, present, absent in (
            ({}, "Structure only", "Entropy log(T) coefficient"),
            ({"alpha": "1/3"}, "CRITICAL", "lambda_m ="),
            (
                {"observation_time": 100, "sampling_interval": 0.1},
                "Sampling scales",
                "Entropy log(T) coefficient",
            ),
        ):
            study = ho.load_study_example("bridge")
            study["analysis"] = settings
            result = ho.compare_configurations(study)
            original = copy.deepcopy(result)
            with mock.patch(
                "homological_observability.phase.predict_phase",
                side_effect=AssertionError("renderer recomputed science"),
            ):
                for renderer in (
                    ho.render_comparison_text,
                    ho.render_comparison_markdown,
                ):
                    text = readable(renderer(result))
                    self.assertIn(present, text)
                    self.assertNotIn(absent, text)
                    self.assertIn("Information relations", text)
                    self.assertIn("Readout changes", text)
                for renderer in (ho.render_text, ho.render_markdown):
                    text = renderer(result["results"]["mixed"])
                    self.assertIn(present, text)
                    self.assertNotIn(absent, text)
            self.assertEqual(result, original)

    def test_finite_scales_torsion_and_scope_are_read_from_records(self):
        study = ho.load_study_example("bridge")
        study["analysis"] = {
            "observation_time": 10,
            "sampling_interval": 0.2,
            "max_layer": 2,
        }
        result = ho.compare_configurations(study)
        # A renderer must preserve finite torsion even where the free rank is 0.
        record = result["results"]["mixed"]
        record["filtration"]["layers"][2]["hidden"]["graded_quotient"].update(
            free_rank=0, torsion_factors=[7]
        )
        record["phase"]["layers"][0]["lambda"] = 1.23456789
        for renderer in (ho.render_text, ho.render_markdown):
            text = renderer(record)
            self.assertIn("1.23456789", text)
            self.assertIn("Z/7", text)
            self.assertIn("PARTIAL_HORIZON", text)
        for renderer in (ho.render_comparison_text, ho.render_comparison_markdown):
            text = readable(renderer(result))
            self.assertIn("Z/7", text)
            self.assertIn("uncomputed layers open", text)
            self.assertIn("Zero free rank can coexist with finite torsion", text)

    def test_all_failed_or_limited_requests_do_not_invent_scales(self):
        for limited in (False, True):
            study = ho.load_study_example("bridge")
            study["analysis"] = {"observation_time": 100, "sampling_interval": 0.1}
            if limited:
                study["analysis"]["max_cycles"] = 1
            else:
                for config in study["configurations"]:
                    config["readouts"] = "invalid"
            result = ho.compare_configurations(study)
            for renderer in (ho.render_comparison_text, ho.render_comparison_markdown):
                text = readable(renderer(result))
                self.assertIn("Observation time: 100.0", text)
                self.assertIn("No sampling results were computed", text)
                self.assertNotIn("lambda_m =", text)
                self.assertNotIn("no hidden integer direction remains", text)

    def test_zero_hidden_configuration_retains_zero_graded_values(self):
        study = ho.load_study_example("bridge")
        study["analysis"] = {"alpha": "1/3"}
        result = ho.compare_configurations(study)
        resolved = next(
            row for row in result["rows"] if row["computed_hidden_rank"] == 0
        )
        raw = result["results"][resolved["id"]]
        self.assertTrue(
            all(layer["hidden_free_rank"] == 0 for layer in raw["phase"]["layers"])
        )
        text = ho.render_markdown(raw)
        self.assertIn(
            "Total entropy log(T) coefficient on the computed horizon: 0.0", text
        )
        self.assertIn("Hidden graded torsion", text)
