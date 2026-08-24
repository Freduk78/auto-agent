"""Regression and mutation tests for the dependency-free package validator."""

from __future__ import annotations

import copy
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if str(PACKAGE_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location(
    "auto_agent_validate", PACKAGE_ROOT / "scripts" / "validate.py"
)
if SPEC is None or SPEC.loader is None:  # pragma: no cover - import guard
    raise RuntimeError("unable to load scripts/validate.py")
validate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validate)
import merge_forward_observations as forward_merge

ROUTE_FIELDS = (
    "mode",
    "reasoning_effort",
    "tool_policy",
    "specialist_route",
    "verification",
    "settings_action",
    "approval_required",
    "agent_policy",
    "execution_disposition",
)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


class PackageCopyTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name) / "auto-agent"
        shutil.copytree(
            PACKAGE_ROOT,
            self.root,
            ignore=shutil.ignore_patterns(".git", "__pycache__", ".coverage"),
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def errors(self) -> list[str]:
        return validate.validate_package(self.root, today=date(2026, 8, 24))

    def assert_package_fails(self, needle: str) -> None:
        errors = self.errors()
        self.assertTrue(
            any(needle in error for error in errors),
            f"expected {needle!r} in validation errors: {errors}",
        )

    def mutate_case_and_runs(self, case_id: str, field: str, value) -> None:
        cases_path = self.root / "tests" / "routing-cases.json"
        cases = read_json(cases_path)
        case = next(item for item in cases if item["id"] == case_id)
        case["expected"][field] = value
        write_json(cases_path, cases)

        observations_path = self.root / "tests" / "forward-test-observations.json"
        observations = read_json(observations_path)
        observed_case = next(
            item for item in observations["observations"] if item["id"] == case_id
        )
        for run in observed_case["runs"]:
            run[field] = value
        write_json(observations_path, observations)

    def case_validation_errors(self) -> list[str]:
        """Validate fixture routes alone, without unrelated package evidence checks."""

        errors: list[str] = []
        vocabulary = read_json(self.root / "contracts" / "v1" / "vocabulary.json")
        policy = read_json(self.root / "contracts" / "v1" / "policy-rules.json")
        profiles = read_json(self.root / "tests" / "capability-profiles.json")
        profile_ids = validate.validate_capability_profiles(profiles, vocabulary, errors)
        validate.validate_cases(
            read_json(self.root / "tests" / "routing-cases.json"),
            vocabulary,
            policy,
            profile_ids,
            errors,
        )
        return errors


class ForwardObservationMergeTests(PackageCopyTestCase):
    def blind_document(self) -> list[dict]:
        cases = read_json(self.root / "tests" / "routing-cases.json")
        return [{"id": case["id"], **case["expected"]} for case in cases]

    def write_blind(self, name: str, document: list[dict] | None = None) -> Path:
        path = self.root / "tests" / f".blind-{name}.json"
        write_json(path, document if document is not None else self.blind_document())
        return path

    @staticmethod
    def configurations(paths: list[Path]) -> list[tuple[str, str, str, Path]]:
        return [
            ("config-economy-a", "codex_subagent", "economy", paths[0]),
            ("config-balanced-b", "codex_subagent", "balanced", paths[1]),
            ("config-frontier-c", "codex_subagent", "frontier", paths[2]),
        ]

    @mock.patch.object(forward_merge, "verify_manifest", return_value=[])
    def test_valid_merge_emits_only_normalized_finite_metadata(self, _verify) -> None:
        paths = [self.write_blind(name) for name in ("a", "b", "c")]
        document = forward_merge.merge_observations(
            self.root, self.configurations(paths)
        )
        self.assertEqual(len(document["observations"]), 39)
        self.assertEqual(set(document), {
            "schema_version",
            "artifact",
            "capability_profile",
            "runs_per_case",
            "evaluator_configurations",
            "observations",
        })
        expected_run_fields = {
            "run",
            "evaluator_configuration",
            "evaluation_outcome",
        } | forward_merge.validate.EXPECTED_ROUTE_KEYS
        for observation in document["observations"]:
            self.assertEqual(set(observation), {"id", "runs"})
            for run in observation["runs"]:
                self.assertEqual(set(run), expected_run_fields)

    @mock.patch.object(forward_merge, "verify_manifest", return_value=[])
    def test_duplicate_blind_input_path_is_rejected(self, _verify) -> None:
        path = self.write_blind("same")
        with self.assertRaisesRegex(
            forward_merge.MergeError, "unique blind input path"
        ):
            forward_merge.merge_observations(
                self.root, self.configurations([path, path, path])
            )

    @mock.patch.object(forward_merge, "verify_manifest", return_value=[])
    def test_extra_raw_field_is_rejected(self, _verify) -> None:
        malformed = self.blind_document()
        malformed[0]["rationale"] = "must not be retained"
        paths = [
            self.write_blind("bad", malformed),
            self.write_blind("b"),
            self.write_blind("c"),
        ]
        with self.assertRaisesRegex(forward_merge.MergeError, "only finite route metadata"):
            forward_merge.merge_observations(
                self.root, self.configurations(paths)
            )

    @mock.patch.object(
        forward_merge,
        "verify_manifest",
        return_value=["artifact bundle digest does not match protected files"],
    )
    def test_stale_manifest_is_rejected_before_merging(self, _verify) -> None:
        paths = [self.write_blind(name) for name in ("a", "b", "c")]
        with self.assertRaisesRegex(forward_merge.MergeError, "artifact manifest is stale"):
            forward_merge.merge_observations(
                self.root, self.configurations(paths)
            )

    @mock.patch.object(forward_merge, "verify_manifest", return_value=[])
    def test_distinct_evaluator_pairs_are_required(self, _verify) -> None:
        paths = [self.write_blind(name) for name in ("a", "b", "c")]
        configurations = [
            (f"config-{name}", "codex_subagent", "economy", path)
            for name, path in zip(("a", "b", "c"), paths, strict=True)
        ]
        with self.assertRaisesRegex(forward_merge.MergeError, "distinct host/model pairs"):
            forward_merge.merge_observations(self.root, configurations)

    def test_blind_input_must_be_ephemeral_and_under_tests(self) -> None:
        with self.assertRaisesRegex(forward_merge.MergeError, "tests/.blind"):
            forward_merge._safe_raw_path(self.root, self.root / "README.md")


class ValidatorRegressionTests(PackageCopyTestCase):
    def test_fully_valid_package(self) -> None:
        self.assertEqual(self.errors(), [])

    def test_missing_required_file(self) -> None:
        (self.root / "README.md").unlink()
        self.assert_package_fails("missing required file: README.md")

    def test_malformed_frontmatter(self) -> None:
        skill = self.root / "SKILL.md"
        skill.write_text(skill.read_text(encoding="utf-8").removeprefix("---\n"))
        self.assert_package_fails("YAML frontmatter")

    def test_stale_artifact_hash_after_skill_change(self) -> None:
        skill = self.root / "SKILL.md"
        skill.write_text(skill.read_text(encoding="utf-8") + "\n<!-- mutation -->\n")
        self.assert_package_fails("artifact bundle digest")

    def test_forward_evidence_helpers_are_protected(self) -> None:
        for relative in (
            "scripts/artifact_manifest.py",
            "scripts/forward_report.py",
            "scripts/merge_forward_observations.py",
        ):
            with self.subTest(relative=relative):
                self.tearDown()
                self.setUp()
                helper = self.root / relative
                helper.write_text(
                    helper.read_text(encoding="utf-8") + "\n# mutation\n",
                    encoding="utf-8",
                )
                self.assert_package_fails("artifact bundle digest")

    def test_stale_observation_artifact_hash(self) -> None:
        path = self.root / "tests" / "forward-test-observations.json"
        document = read_json(path)
        document["artifact"]["bundle_sha256"] = "0" * 64
        write_json(path, document)
        self.assert_package_fails("observations artifact digest")

    def test_every_observed_route_field_is_compared(self) -> None:
        alternate = {
            "mode": "BALANCED",
            "reasoning_effort": "medium",
            "tool_policy": "targeted",
            "specialist_route": "diagram",
            "verification": "standard",
            "settings_action": "unchanged",
            "approval_required": True,
            "agent_policy": "bounded",
            "execution_disposition": "stop",
        }
        for field in ROUTE_FIELDS:
            with self.subTest(field=field):
                self.tearDown()
                self.setUp()
                path = self.root / "tests" / "forward-test-observations.json"
                document = read_json(path)
                run = next(
                    item for item in document["observations"] if item["id"] == "T01"
                )["runs"][0]
                run[field] = alternate[field]
                write_json(path, document)
                self.assert_package_fails("evaluation_outcome")

    def test_explicit_complete_route_variant_is_accepted(self) -> None:
        cases_path = self.root / "tests" / "routing-cases.json"
        cases = read_json(cases_path)
        case = next(item for item in cases if item["id"] == "T01")
        variant = copy.deepcopy(case["expected"])
        variant["reasoning_effort"] = "low"
        case["permitted_variants"] = [variant]
        write_json(cases_path, cases)
        self.assertEqual(self.case_validation_errors(), [])

        observations_path = self.root / "tests" / "forward-test-observations.json"
        observations = read_json(observations_path)
        for run in next(
            item for item in observations["observations"] if item["id"] == "T01"
        )["runs"]:
            run["reasoning_effort"] = "low"
            run["evaluation_outcome"] = "permitted_variant"
        write_json(observations_path, observations)
        self.assertFalse(
            any("T01 run" in error and "evaluation_outcome" in error for error in self.errors())
        )

    def test_variants_must_be_complete_unique_and_non_vague(self) -> None:
        cases_path = self.root / "tests" / "routing-cases.json"
        cases = read_json(cases_path)
        case = next(item for item in cases if item["id"] == "T01")
        canonical = copy.deepcopy(case["expected"])
        incomplete = copy.deepcopy(canonical)
        del incomplete["verification"]
        vague = copy.deepcopy(canonical)
        vague["mode"] = "as_needed"
        case["permitted_variants"] = [canonical, incomplete, vague]
        write_json(cases_path, cases)
        errors = self.case_validation_errors()
        self.assertTrue(any("duplicates the canonical" in error for error in errors))
        self.assertTrue(any("missing route fields" in error for error in errors))
        self.assertTrue(any("invalid mode" in error for error in errors))

    def test_variants_must_preserve_case_safety_invariants(self) -> None:
        cases_path = self.root / "tests" / "routing-cases.json"
        cases = read_json(cases_path)
        case = next(item for item in cases if item["id"] == "T10")
        variant = copy.deepcopy(case["expected"])
        variant["reasoning_effort"] = "high"
        case["permitted_variants"] = [variant]
        write_json(cases_path, cases)
        self.assertTrue(
            any("maximum reasoning" in error for error in self.case_validation_errors())
        )

    def test_adversarial_cases_require_structured_safety_constraints(self) -> None:
        cases_path = self.root / "tests" / "routing-cases.json"
        cases = read_json(cases_path)
        case = next(item for item in cases if item["id"] == "T19")
        case.pop("safety_constraints")
        write_json(cases_path, cases)
        self.assertTrue(
            any("requires structured safety_constraints" in error for error in self.case_validation_errors())
        )

    def test_permitted_variant_count_is_bounded(self) -> None:
        cases_path = self.root / "tests" / "routing-cases.json"
        cases = read_json(cases_path)
        case = next(item for item in cases if item["id"] == "T01")
        variants = []
        for index in range(6):
            variant = copy.deepcopy(case["expected"])
            variant["escalation_count"] = index % 3
            variant["reasoning_effort"] = ("low", "medium")[index % 2]
            variants.append(variant)
        case["permitted_variants"] = variants
        write_json(cases_path, cases)
        self.assertTrue(
            any("1 to 5 complete routes" in error for error in self.case_validation_errors())
        )

    def test_critical_mode_always_uses_the_full_profile(self) -> None:
        cases_path = self.root / "tests" / "routing-cases.json"
        cases = read_json(cases_path)
        case = next(item for item in cases if item["id"] == "T01")
        variant = copy.deepcopy(case["expected"])
        variant["mode"] = "CRITICAL"
        variant["reasoning_effort"] = "high"
        variant["tool_policy"] = "evidence_led"
        variant["verification"] = "critical"
        case["permitted_variants"] = [variant]
        write_json(cases_path, cases)
        self.assertTrue(
            any("CRITICAL route must use maximum reasoning" in error for error in self.case_validation_errors())
        )

    def test_cross_product_of_permitted_field_values_is_rejected(self) -> None:
        cases_path = self.root / "tests" / "routing-cases.json"
        cases = read_json(cases_path)
        case = next(item for item in cases if item["id"] == "T01")
        variant = copy.deepcopy(case["expected"])
        variant["reasoning_effort"] = "low"
        variant["verification"] = "standard"
        case["permitted_variants"] = [variant]
        write_json(cases_path, cases)

        observations_path = self.root / "tests" / "forward-test-observations.json"
        observations = read_json(observations_path)
        run = next(
            item for item in observations["observations"] if item["id"] == "T01"
        )["runs"][0]
        run["verification"] = "standard"
        write_json(observations_path, observations)
        self.assert_package_fails("evaluation_outcome")

    def test_field_outside_all_permitted_routes_is_reported_by_field(self) -> None:
        cases_path = self.root / "tests" / "routing-cases.json"
        cases = read_json(cases_path)
        case = next(item for item in cases if item["id"] == "T01")
        variant = copy.deepcopy(case["expected"])
        variant["reasoning_effort"] = "low"
        case["permitted_variants"] = [variant]
        write_json(cases_path, cases)

        observations_path = self.root / "tests" / "forward-test-observations.json"
        observations = read_json(observations_path)
        run = next(
            item for item in observations["observations"] if item["id"] == "T01"
        )["runs"][0]
        run["reasoning_effort"] = "high"
        write_json(observations_path, observations)
        self.assert_package_fails("evaluation_outcome")

    def test_incomplete_observation_is_rejected(self) -> None:
        path = self.root / "tests" / "forward-test-observations.json"
        document = read_json(path)
        del document["observations"][0]["runs"][0]["tool_policy"]
        write_json(path, document)
        self.assert_package_fails("missing route fields")

    def test_observation_counts_are_exact(self) -> None:
        path = self.root / "tests" / "forward-test-observations.json"
        document = read_json(path)
        document["observations"].pop()
        write_json(path, document)
        self.assert_package_fails("observations missing cases")

    def test_forward_report_is_reconciled_exactly(self) -> None:
        path = self.root / "tests" / "forward-test-report.md"
        path.write_text(path.read_text(encoding="utf-8") + "\nFalse summary.\n", encoding="utf-8")
        self.assert_package_fails("does not exactly match normalized observations")

    def test_three_isolated_runs_and_multiple_configs_are_required(self) -> None:
        path = self.root / "tests" / "forward-test-observations.json"
        document = read_json(path)
        document["observations"][0]["runs"] = document["observations"][0]["runs"][:2]
        write_json(path, document)
        self.assert_package_fails("must contain exactly 3 runs")

    def test_evaluator_configurations_must_have_distinct_host_model_pairs(self) -> None:
        path = self.root / "tests" / "forward-test-observations.json"
        document = read_json(path)
        for config in document["evaluator_configurations"]:
            config["host_class"] = "codex_subagent"
            config["model_class"] = "balanced"
        write_json(path, document)
        self.assert_package_fails("distinct host/model pairs")

    def test_each_case_must_use_distinct_pairs_not_an_unused_declaration(self) -> None:
        path = self.root / "tests" / "forward-test-observations.json"
        document = read_json(path)
        for config in document["evaluator_configurations"]:
            config["host_class"] = "codex_subagent"
            config["model_class"] = "balanced"
        document["evaluator_configurations"].append(
            {
                "id": "config-unused-frontier",
                "host_class": "codex_subagent",
                "model_class": "frontier",
                "isolation": "fresh_context_blind_to_expected",
            }
        )
        write_json(path, document)
        self.assert_package_fails("T01 requires at least 2 distinct host/model pairs")
        self.assert_package_fails("every declared evaluator configuration must be used")

    def test_safety_relevant_vocabulary_is_exact(self) -> None:
        path = self.root / "contracts" / "v1" / "vocabulary.json"
        document = read_json(path)
        document["tool_policy"].append("automatic_unbounded")
        write_json(path, document)
        self.assert_package_fails("approved finite contract")

    def test_decision_schema_behavior_cannot_move_to_an_unrelated_branch(self) -> None:
        path = self.root / "references" / "decision-record.schema.json"
        document = read_json(path)
        critical = next(
            rule
            for rule in document["allOf"]
            if rule.get("if", {}).get("properties", {}).get("mode", {}).get("const")
            == "CRITICAL"
        )
        critical["then"]["properties"].pop("tool_policy")
        document["description"] += " tool_policy gated"
        write_json(path, document)
        self.assert_package_fails("exact behavioral invariant: CRITICAL profile")

    def test_adapter_schema_control_map_must_be_closed(self) -> None:
        path = self.root / "references" / "adapter-manifest.schema.json"
        document = read_json(path)
        document["properties"]["capability_contract"]["properties"]["control_values"][
            "additionalProperties"
        ] = True
        write_json(path, document)
        self.assert_package_fails("control_values must be a closed control map")

    def test_ci_analyzer_lock_requires_hashes(self) -> None:
        path = self.root / "requirements-dev.lock"
        text = path.read_text(encoding="utf-8")
        first, remainder = text.split("anyio==", 1)
        first = first.replace("--hash=sha256:", "--removed-hash=sha256:")
        path.write_text(first + "anyio==" + remainder, encoding="utf-8")
        self.assert_package_fails("package lacks hashes")

    def test_implicit_invocation_is_disabled_for_trial_release(self) -> None:
        path = self.root / "agents" / "openai.yaml"
        text = path.read_text(encoding="utf-8").replace(
            "allow_implicit_invocation: false", "allow_implicit_invocation: true"
        )
        path.write_text(text, encoding="utf-8")
        self.assert_package_fails("implicit invocation must remain disabled")

    def test_execution_budget_cannot_allow_recursive_expansion(self) -> None:
        path = self.root / "contracts" / "v1" / "execution-budget.schema.json"
        document = read_json(path)
        document["properties"]["recursive_expansion_allowed"]["const"] = True
        write_json(path, document)
        self.assert_package_fails("execution-budget schema weakens invariant")

    def test_execution_budget_cannot_bypass_approval(self) -> None:
        path = self.root / "contracts" / "v1" / "execution-budget.schema.json"
        document = read_json(path)
        document["properties"]["approval_bypass_allowed"]["const"] = True
        write_json(path, document)
        self.assert_package_fails("execution-budget schema weakens invariant")

    def test_execution_budget_cannot_ignore_blocked_required_dependency(self) -> None:
        path = self.root / "contracts" / "v1" / "execution-budget.schema.json"
        document = read_json(path)
        document["properties"]["required_dependency_blocked_stops"]["const"] = False
        write_json(path, document)
        self.assert_package_fails("execution-budget schema weakens invariant")

    def test_execution_budget_sources_are_exact_and_trusted(self) -> None:
        path = self.root / "contracts" / "v1" / "execution-budget.schema.json"
        document = read_json(path)
        document["properties"]["source"]["enum"].append("prompt_claim")
        write_json(path, document)
        self.assert_package_fails("source enum differs from trusted policy sources")

    def test_execution_budget_requires_version_and_source(self) -> None:
        for field in ("schema_version", "source"):
            with self.subTest(field=field):
                self.tearDown()
                self.setUp()
                path = self.root / "contracts" / "v1" / "execution-budget.schema.json"
                document = read_json(path)
                document["required"].remove(field)
                write_json(path, document)
                self.assert_package_fails(
                    "execution-budget schema required fields differ from the v1 contract"
                )

    def test_workflow_action_must_use_full_commit_sha(self) -> None:
        path = self.root / ".github" / "workflows" / "quality-gate.yml"
        text = path.read_text(encoding="utf-8")
        text = text.replace(
            "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
            "actions/checkout@v7",
            1,
        )
        path.write_text(text, encoding="utf-8")
        self.assert_package_fails("not pinned to a full commit SHA")

    def test_workflow_cannot_grant_write_permission(self) -> None:
        path = self.root / ".github" / "workflows" / "quality-gate.yml"
        text = path.read_text(encoding="utf-8").replace(
            "permissions:\n  contents: read",
            "permissions:\n  contents: write",
            1,
        )
        path.write_text(text, encoding="utf-8")
        self.assert_package_fails("grants write permission")


class SafetyMutationTests(PackageCopyTestCase):
    def test_critical_fixture_cannot_be_weakened_even_if_runs_agree(self) -> None:
        self.mutate_case_and_runs("T10", "mode", "BALANCED")
        self.mutate_case_and_runs("T10", "verification", "standard")
        self.assert_package_fails("safety tags require CRITICAL")

    def test_unavailable_capability_cannot_be_marked_applied(self) -> None:
        self.mutate_case_and_runs("T25", "settings_action", "applied")
        self.assert_package_fails("unavailable or stale capability must be recommend_only")

    def test_unknown_material_cost_cannot_skip_approval(self) -> None:
        self.mutate_case_and_runs("T23", "settings_action", "applied")
        self.mutate_case_and_runs("T23", "approval_required", False)
        self.assert_package_fails("unknown material cost must require approval")

    def test_explicit_maximum_effort_cannot_be_silently_lowered(self) -> None:
        cases_path = self.root / "tests" / "routing-cases.json"
        cases = read_json(cases_path)
        case = next(item for item in cases if item["id"] == "T16")
        case["expected"]["reasoning_effort"] = "high"
        write_json(cases_path, cases)
        self.assertTrue(
            any(
                "explicit maximum request must retain maximum" in error
                for error in self.case_validation_errors()
            )
        )

    def test_specialist_mode_requires_a_route(self) -> None:
        self.mutate_case_and_runs("T17", "specialist_route", None)
        self.assert_package_fails("SPECIALIST route must name specialist_route")

    def test_prompt_injection_cannot_change_authority(self) -> None:
        self.mutate_case_and_runs("T19", "settings_action", "applied")
        self.mutate_case_and_runs("T19", "agent_policy", "bounded")
        self.assert_package_fails("untrusted content must preserve authority")

    def test_prompt_injection_cannot_expand_tools_even_when_labeled_genuine(self) -> None:
        path = self.root / "tests" / "forward-test-observations.json"
        document = read_json(path)
        run = next(item for item in document["observations"] if item["id"] == "T19")[
            "runs"
        ][0]
        run["tool_policy"] = "evidence_led"
        run["evaluation_outcome"] = "genuine_misclassification"
        write_json(path, document)
        self.assert_package_fails("violates safety_constraints for tool_policy")

    def test_more_than_two_escalations_is_rejected(self) -> None:
        path = self.root / "tests" / "forward-test-observations.json"
        document = read_json(path)
        document["observations"][0]["runs"][0]["escalation_count"] = 3
        write_json(path, document)
        self.assert_package_fails("escalation_count")

    def test_reasoning_failure_requires_trusted_out_of_band_context(self) -> None:
        cases_path = self.root / "tests" / "routing-cases.json"
        cases = read_json(cases_path)
        case = next(item for item in cases if item["id"] == "T38")
        case.pop("context")
        write_json(cases_path, cases)
        self.assertTrue(
            any(
                "requires complete trusted harness context" in error
                for error in self.case_validation_errors()
            )
        )

    def test_reasoning_failure_context_is_closed_and_provenance_limited(self) -> None:
        cases_path = self.root / "tests" / "routing-cases.json"
        cases = read_json(cases_path)
        case = next(item for item in cases if item["id"] == "T38")
        case["context"]["prompt_claim"] = "prior failure"
        case["context"]["source"] = "user_prompt"
        write_json(cases_path, cases)
        errors = self.case_validation_errors()
        self.assertTrue(
            any("requires complete trusted harness context" in error for error in errors)
        )

    def test_reasoning_failure_context_rejects_impossible_mode_count_state(self) -> None:
        cases_path = self.root / "tests" / "routing-cases.json"
        cases = read_json(cases_path)
        case = next(item for item in cases if item["id"] == "T38")
        case["context"]["prior_mode"] = "FAST"
        case["context"]["prior_router_escalation_count"] = 1
        write_json(cases_path, cases)
        self.assertTrue(
            any(
                "trusted harness context has an impossible mode/count state" in error
                for error in self.case_validation_errors()
            )
        )

    def test_reasoning_failure_count_advances_only_trusted_state(self) -> None:
        cases_path = self.root / "tests" / "routing-cases.json"
        cases = read_json(cases_path)
        case = next(item for item in cases if item["id"] == "T38")
        case["expected"]["escalation_count"] = 0
        write_json(cases_path, cases)
        self.assertTrue(
            any(
                "must advance trusted prior router state exactly once" in error
                for error in self.case_validation_errors()
            )
        )

    def test_reasoning_failure_route_advances_exactly_one_mode(self) -> None:
        cases_path = self.root / "tests" / "routing-cases.json"
        cases = read_json(cases_path)
        case = next(item for item in cases if item["id"] == "T38")
        case["expected"].update(
            {
                "mode": "CRITICAL",
                "reasoning_effort": "maximum",
                "tool_policy": "gated",
                "verification": "critical",
            }
        )
        write_json(cases_path, cases)
        self.assertTrue(
            any(
                "reasoning failure must escalate exactly one mode" in error
                for error in self.case_validation_errors()
            )
        )

    def test_observed_escalation_count_is_compared(self) -> None:
        path = self.root / "tests" / "forward-test-observations.json"
        document = read_json(path)
        document["observations"][0]["runs"][0]["escalation_count"] = 1
        write_json(path, document)
        self.assert_package_fails("evaluation_outcome")

    def test_observation_cannot_store_prompt_or_identifier(self) -> None:
        path = self.root / "tests" / "forward-test-observations.json"
        document = read_json(path)
        document["observations"][0]["runs"][0]["prompt"] = "forbidden"
        write_json(path, document)
        self.assert_package_fails("unexpected fields")

    def test_recursive_budget_bypass_is_rejected(self) -> None:
        self.mutate_case_and_runs("T29", "agent_policy", "bounded")
        self.assert_package_fails("budget case must remain unapplied")

    def test_system_policy_cannot_be_bypassed(self) -> None:
        self.mutate_case_and_runs("T32", "tool_policy", "targeted")
        self.assert_package_fails("system policy must override")

    def test_system_policy_blocked_current_fact_cannot_proceed(self) -> None:
        self.mutate_case_and_runs("T32", "execution_disposition", "proceed")
        self.assert_package_fails("violates safety_constraints for execution_disposition")

    def test_project_policy_cannot_enable_agents(self) -> None:
        self.mutate_case_and_runs("T35", "agent_policy", "host_confirmed_only")
        self.assert_package_fails("project policy must override")

    def test_project_policy_cannot_enable_tools_when_outcome_is_honest(self) -> None:
        path = self.root / "tests" / "forward-test-observations.json"
        document = read_json(path)
        run = next(item for item in document["observations"] if item["id"] == "T35")[
            "runs"
        ][0]
        run["tool_policy"] = "targeted"
        run["evaluation_outcome"] = "genuine_misclassification"
        write_json(path, document)
        self.assert_package_fails("project policy must override router tools and agents")

    def test_missing_access_stops_tool_retries(self) -> None:
        self.mutate_case_and_runs("T31", "tool_policy", "targeted")
        self.assert_package_fails("required dependency, missing access, or repeated failure must stop")

    def test_missing_access_stops_agents_and_specialists(self) -> None:
        path = self.root / "tests" / "forward-test-observations.json"
        document = read_json(path)
        run = next(item for item in document["observations"] if item["id"] == "T31")[
            "runs"
        ][0]
        run["agent_policy"] = "host_confirmed_only"
        run["specialist_route"] = "browser"
        run["evaluation_outcome"] = "genuine_misclassification"
        write_json(path, document)
        self.assert_package_fails("must stop settings, tools, agents, and escalation")

    def test_critical_missing_access_requires_explicit_stop(self) -> None:
        self.mutate_case_and_runs("T39", "execution_disposition", "proceed")
        self.assert_package_fails("required dependency, missing access, or repeated failure must stop")

    def test_required_dependency_stop_survives_oracle_mutation(self) -> None:
        self.mutate_case_and_runs("T32", "execution_disposition", "proceed")
        cases_path = self.root / "tests" / "routing-cases.json"
        cases = read_json(cases_path)
        case = next(item for item in cases if item["id"] == "T32")
        case["safety_constraints"]["allowed_execution_dispositions"] = ["proceed"]
        write_json(cases_path, cases)
        self.assert_package_fails(
            "required dependency, missing access, or repeated failure must stop"
        )

    def test_critical_stop_rejects_each_execution_channel(self) -> None:
        mutations = {
            "settings_action": "applied",
            "agent_policy": "host_confirmed_only",
            "specialist_route": "browser",
            "escalation_count": 1,
        }
        for field, value in mutations.items():
            with self.subTest(field=field):
                self.tearDown()
                self.setUp()
                self.mutate_case_and_runs("T39", field, value)
                self.assert_package_fails("T39")

    def test_unconfirmed_agent_controls_cannot_be_marked_bounded(self) -> None:
        self.mutate_case_and_runs("T06", "agent_policy", "bounded")
        self.assert_package_fails("unconfirmed agent controls")


class EvaluationOutcomeTests(unittest.TestCase):
    """Outcome classification tests independent of checked-in forward evidence."""

    @staticmethod
    def fast_route() -> dict:
        return {
            "mode": "FAST",
            "reasoning_effort": "minimal",
            "tool_policy": "none",
            "specialist_route": None,
            "verification": "focused",
            "settings_action": "recommend_only",
            "approval_required": False,
            "agent_policy": "host_confirmed_only",
            "execution_disposition": "proceed",
            "escalation_count": 0,
        }

    def test_every_route_field_mutation_rejects_an_exact_label(self) -> None:
        case = {"expected": self.fast_route()}
        replacements = {
            "mode": "BALANCED",
            "reasoning_effort": "low",
            "tool_policy": "local_only",
            "specialist_route": "diagram",
            "verification": "standard",
            "settings_action": "unchanged",
            "approval_required": True,
            "agent_policy": "none",
            "execution_disposition": "stop",
            "escalation_count": 1,
        }
        for field, replacement in replacements.items():
            with self.subTest(field=field):
                route = self.fast_route()
                route[field] = replacement
                errors: list[str] = []
                validate.validate_evaluation_outcome(case, route, "exact", "test", errors)
                self.assertTrue(errors)
                self.assertIn("does not match computed", errors[0])

    def test_exact_permitted_and_genuine_labels_are_computed_from_full_tuples(self) -> None:
        canonical = self.fast_route()
        variant = copy.deepcopy(canonical)
        variant["tool_policy"] = "local_only"
        case = {"expected": canonical, "permitted_variants": [variant]}
        self.assertEqual(validate.classify_evaluation_outcome(case, canonical), "exact")
        self.assertEqual(
            validate.classify_evaluation_outcome(case, variant), "permitted_variant"
        )
        mismatch = copy.deepcopy(canonical)
        mismatch["tool_policy"] = "targeted"
        self.assertEqual(
            validate.classify_evaluation_outcome(case, mismatch),
            "genuine_misclassification",
        )

    def test_mislabeled_outcomes_are_rejected(self) -> None:
        case = {"expected": self.fast_route()}
        errors: list[str] = []
        validate.validate_evaluation_outcome(
            case, self.fast_route(), "genuine_misclassification", "test", errors
        )
        self.assertTrue(errors)
        self.assertIn("does not match computed 'exact'", errors[0])

    def test_safe_upward_mode_uses_consistent_profile_and_preserves_boundaries(self) -> None:
        base = self.fast_route()
        observed = copy.deepcopy(base)
        observed.update(
            {
                "mode": "BALANCED",
                "reasoning_effort": "medium",
                "verification": "standard",
                "approval_required": True,
                "agent_policy": "none",
            }
        )
        self.assertEqual(
            validate.classify_evaluation_outcome({"expected": base}, observed),
            "safe_upward",
        )

    def test_safe_upward_cannot_expand_tools_or_apply_a_costlier_profile(self) -> None:
        base = self.fast_route()
        for tool_policy in ("local_only", "targeted", "evidence_led", "specialist"):
            with self.subTest(tool_policy=tool_policy):
                observed = copy.deepcopy(base)
                observed.update(
                    {
                        "mode": "BALANCED",
                        "reasoning_effort": "medium",
                        "verification": "standard",
                        "tool_policy": tool_policy,
                    }
                )
                self.assertEqual(
                    validate.classify_evaluation_outcome({"expected": base}, observed),
                    "genuine_misclassification",
                )
        applied = copy.deepcopy(base)
        applied.update(
            {
                "mode": "BALANCED",
                "reasoning_effort": "medium",
                "verification": "standard",
                "settings_action": "applied",
            }
        )
        base["settings_action"] = "applied"
        self.assertEqual(
            validate.classify_evaluation_outcome({"expected": base}, applied),
            "genuine_misclassification",
        )

    def test_same_mode_only_allows_explicit_safety_tightenings(self) -> None:
        base = self.fast_route()
        observed = copy.deepcopy(base)
        observed["approval_required"] = True
        observed["agent_policy"] = "none"
        self.assertEqual(
            validate.classify_evaluation_outcome({"expected": base}, observed),
            "safe_upward",
        )

    def test_critical_safe_upward_requires_the_complete_critical_profile(self) -> None:
        base = self.fast_route()
        base.update(
            {
                "mode": "DEEP",
                "reasoning_effort": "high",
                "verification": "deep",
                "tool_policy": "targeted",
            }
        )
        critical = copy.deepcopy(base)
        critical.update(
            {
                "mode": "CRITICAL",
                "reasoning_effort": "maximum",
                "verification": "critical",
                "tool_policy": "gated",
            }
        )
        case = {"expected": base}
        self.assertEqual(
            validate.classify_evaluation_outcome(case, critical), "safe_upward"
        )
        critical["tool_policy"] = "evidence_led"
        self.assertEqual(
            validate.classify_evaluation_outcome(case, critical),
            "genuine_misclassification",
        )

    def test_safe_upward_never_lowers_explicit_reasoning_effort(self) -> None:
        base = self.fast_route()
        base["reasoning_effort"] = "maximum"
        observed = copy.deepcopy(base)
        observed.update(
            {
                "mode": "BALANCED",
                "reasoning_effort": "medium",
                "verification": "standard",
            }
        )
        self.assertEqual(
            validate.classify_evaluation_outcome({"expected": base}, observed),
            "genuine_misclassification",
        )
        observed["reasoning_effort"] = "maximum"
        self.assertEqual(
            validate.classify_evaluation_outcome({"expected": base}, observed),
            "safe_upward",
        )

    def test_downward_and_missing_specialist_routes_are_genuine(self) -> None:
        deep = self.fast_route()
        deep.update({"mode": "DEEP", "reasoning_effort": "high", "verification": "deep"})
        downward = self.fast_route()
        self.assertEqual(
            validate.classify_evaluation_outcome({"expected": deep}, downward),
            "genuine_misclassification",
        )
        specialist = self.fast_route()
        specialist.update(
            {
                "mode": "SPECIALIST",
                "tool_policy": "specialist",
                "specialist_route": "diagram",
                "verification": "specialist",
            }
        )
        missing_route = copy.deepcopy(specialist)
        missing_route["specialist_route"] = None
        self.assertEqual(
            validate.classify_evaluation_outcome({"expected": specialist}, missing_route),
            "genuine_misclassification",
        )
        policy = read_json(PACKAGE_ROOT / "contracts" / "v1" / "policy-rules.json")
        errors: list[str] = []
        validate.validate_case_semantics({}, missing_route, policy, "test", errors)
        self.assertTrue(any("specialist tool policy" in error for error in errors))

    def test_safety_mismatch_still_fails_even_when_honestly_labeled(self) -> None:
        critical_case = {"tags": ["security"], "expected": self.fast_route()}
        observed = self.fast_route()
        errors: list[str] = []
        validate.validate_case_semantics(critical_case, observed, {"critical_tags": ["security"]}, "test", errors)
        self.assertTrue(any("safety tags require CRITICAL" in error for error in errors))
        self.assertEqual(
            validate.classify_evaluation_outcome(critical_case, observed),
            "exact",
        )


class DecisionRecordSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.vocabulary = read_json(PACKAGE_ROOT / "contracts" / "v1" / "vocabulary.json")
        cls.schema = read_json(PACKAGE_ROOT / "references" / "decision-record.schema.json")

    def valid_record(self) -> dict:
        return {
            "schema_version": "1.0.0",
            "mode": "FAST",
            "reason_codes": ["mechanical_task"],
            "execution_disposition": "proceed",
            "settings_action": "recommend_only",
            "capability_status": "unavailable",
            "cost_status": "unchanged",
            "budget_authorization": "not_required",
            "reasoning_effort": "low",
            "latency_preference": "fastest",
            "context_policy": "minimum_sufficient",
            "tool_policy": "none",
            "agent_policy": "none",
            "specialist_route": None,
            "verification": "focused",
            "response_style": "concise",
            "route_confidence": "high",
            "approval_required": False,
            "escalation_count": 0,
        }

    def errors(self, record: dict) -> list[str]:
        return validate.validate_decision_record(record, self.schema, self.vocabulary)

    def test_valid_decision_record(self) -> None:
        self.assertEqual(self.errors(self.valid_record()), [])

    def test_extra_or_sensitive_fields_are_rejected(self) -> None:
        for field in ("prompt", "user_id", "secret", "chain_of_thought"):
            with self.subTest(field=field):
                record = self.valid_record()
                record[field] = "must-not-be-stored"
                self.assertTrue(self.errors(record))

    def test_critical_reason_code_enforces_critical_mode(self) -> None:
        record = self.valid_record()
        record["reason_codes"] = ["sensitive_domain:payments"]
        self.assertTrue(self.errors(record))

    def test_critical_record_requires_complete_profile(self) -> None:
        record = self.valid_record()
        record.update(
            {
                "mode": "CRITICAL",
                "reason_codes": ["sensitive_domain:payments"],
                "reasoning_effort": "maximum",
                "tool_policy": "gated",
                "verification": "critical",
            }
        )
        self.assertEqual(self.errors(record), [])
        for field, weakened in (
            ("reasoning_effort", "high"),
            ("tool_policy", "targeted"),
            ("verification", "deep"),
        ):
            with self.subTest(field=field):
                mutation = copy.deepcopy(record)
                mutation[field] = weakened
                self.assertTrue(self.errors(mutation))

    def test_stop_reasons_cannot_continue_execution(self) -> None:
        for reason in (
            "missing_access",
            "repeated_failure",
            "required_dependency_blocked",
        ):
            with self.subTest(reason=reason):
                record = self.valid_record()
                record.update(
                    {
                        "reason_codes": [reason],
                        "execution_disposition": "proceed",
                        "settings_action": "applied",
                        "capability_status": "confirmed",
                        "budget_authorization": "confirmed",
                        "tool_policy": "targeted",
                        "agent_policy": "bounded",
                        "specialist_route": "browser",
                        "escalation_count": 1,
                    }
                )
                self.assertTrue(
                    any("execution_disposition stop" in error for error in self.errors(record))
                )

    def test_critical_missing_access_is_truthfully_stopped_without_weakening_profile(self) -> None:
        record = self.valid_record()
        record.update(
            {
                "mode": "CRITICAL",
                "reason_codes": ["sensitive_domain:payments", "missing_access"],
                "execution_disposition": "stop",
                "reasoning_effort": "maximum",
                "tool_policy": "gated",
                "verification": "critical",
            }
        )
        self.assertEqual(self.errors(record), [])
        mutation = copy.deepcopy(record)
        mutation["execution_disposition"] = "proceed"
        self.assertTrue(self.errors(mutation))
        mutation = copy.deepcopy(record)
        mutation["agent_policy"] = "host_confirmed_only"
        self.assertTrue(self.errors(mutation))
        mutation = copy.deepcopy(record)
        mutation.update(
            {
                "settings_action": "applied",
                "capability_status": "confirmed",
                "budget_authorization": "confirmed",
            }
        )
        self.assertTrue(self.errors(mutation))
        mutation = copy.deepcopy(record)
        mutation["specialist_route"] = "browser"
        self.assertTrue(self.errors(mutation))
        mutation = copy.deepcopy(record)
        mutation["escalation_count"] = 1
        self.assertTrue(self.errors(mutation))
        mutation = copy.deepcopy(record)
        mutation.update(
            {
                "mode": "DEEP",
                "reason_codes": ["missing_access"],
                "reasoning_effort": "high",
                "verification": "deep",
            }
        )
        self.assertTrue(self.errors(mutation))

    def test_untrusted_reason_cannot_apply_or_expand_agents(self) -> None:
        record = self.valid_record()
        record.update(
            {
                "reason_codes": ["untrusted_content"],
                "settings_action": "applied",
                "capability_status": "confirmed",
                "budget_authorization": "confirmed",
                "agent_policy": "bounded",
            }
        )
        self.assertTrue(any("untrusted content" in error for error in self.errors(record)))

    def test_unavailable_and_stale_reasons_fail_closed(self) -> None:
        unavailable = self.valid_record()
        unavailable.update(
            {
                "reason_codes": ["capability_unavailable"],
                "capability_status": "confirmed",
                "settings_action": "applied",
                "budget_authorization": "confirmed",
            }
        )
        self.assertTrue(any("unavailable capability" in error for error in self.errors(unavailable)))
        stale = self.valid_record()
        stale.update(
            {
                "reason_codes": ["stale_adapter"],
                "capability_status": "confirmed",
                "settings_action": "applied",
                "budget_authorization": "confirmed",
            }
        )
        self.assertTrue(any("stale adapter" in error for error in self.errors(stale)))

    def test_applied_requires_confirmed_capability_and_budget(self) -> None:
        record = self.valid_record()
        record["settings_action"] = "applied"
        self.assertTrue(self.errors(record))

    def test_unknown_cost_cannot_apply_even_with_confirmed_budget(self) -> None:
        record = self.valid_record()
        record.update(
            {
                "settings_action": "applied",
                "capability_status": "confirmed",
                "cost_status": "unknown",
                "budget_authorization": "confirmed",
            }
        )
        self.assertTrue(self.errors(record))

    def test_escalation_limit_is_enforced(self) -> None:
        record = self.valid_record()
        record["escalation_count"] = 3
        self.assertTrue(self.errors(record))

    def test_specialist_tool_policy_requires_a_route(self) -> None:
        record = self.valid_record()
        record["tool_policy"] = "specialist"
        self.assertTrue(
            any("specialist tool policy" in error for error in self.errors(record))
        )


class AdapterManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = read_json(
            PACKAGE_ROOT / "references" / "adapters" / "openai.json"
        )

    def test_current_matching_adapter_can_be_considered(self) -> None:
        action = validate.resolve_adapter_action(
            self.manifest,
            today=date.fromisoformat(self.manifest["reviewed_at"]),
            runtime_adapter_id=self.manifest["adapter_id"],
            runtime_schema_version=self.manifest["schema_version"],
            runtime_fingerprint=self.manifest["capability_fingerprint"],
            runtime_provenance_validated=True,
            requested_controls={"reasoning_effort": "high"},
        )
        self.assertEqual(action, "eligible")

    def test_expired_adapter_fails_closed(self) -> None:
        action = validate.resolve_adapter_action(
            self.manifest,
            today=date.fromisoformat(self.manifest["expires_at"]) + timedelta(days=1),
            runtime_adapter_id=self.manifest["adapter_id"],
            runtime_schema_version=self.manifest["schema_version"],
            runtime_fingerprint=self.manifest["capability_fingerprint"],
            runtime_provenance_validated=True,
            requested_controls={},
        )
        self.assertEqual(action, "recommend_only")

    def test_future_review_date_fails_closed(self) -> None:
        action = validate.resolve_adapter_action(
            self.manifest,
            today=date.fromisoformat(self.manifest["reviewed_at"]) - timedelta(days=1),
            runtime_adapter_id=self.manifest["adapter_id"],
            runtime_schema_version=self.manifest["schema_version"],
            runtime_fingerprint=self.manifest["capability_fingerprint"],
            runtime_provenance_validated=True,
            requested_controls={},
        )
        self.assertEqual(action, "recommend_only")

    def test_overlong_adapter_lifetime_fails_closed(self) -> None:
        manifest = copy.deepcopy(self.manifest)
        reviewed = date.fromisoformat(manifest["reviewed_at"])
        manifest["expires_at"] = (
            reviewed + timedelta(days=validate.MAX_ADAPTER_TTL_DAYS + 1)
        ).isoformat()
        action = validate.resolve_adapter_action(
            manifest,
            today=reviewed,
            runtime_adapter_id=manifest["adapter_id"],
            runtime_schema_version=manifest["schema_version"],
            runtime_fingerprint=manifest["capability_fingerprint"],
            runtime_provenance_validated=True,
            requested_controls={},
        )
        self.assertEqual(action, "recommend_only")

    def test_mismatched_fingerprint_fails_closed(self) -> None:
        action = validate.resolve_adapter_action(
            self.manifest,
            today=date.fromisoformat(self.manifest["reviewed_at"]),
            runtime_adapter_id=self.manifest["adapter_id"],
            runtime_schema_version=self.manifest["schema_version"],
            runtime_fingerprint="sha256:" + "0" * 64,
            runtime_provenance_validated=True,
            requested_controls={},
        )
        self.assertEqual(action, "recommend_only")

    def test_unsupported_control_fails_closed(self) -> None:
        action = validate.resolve_adapter_action(
            self.manifest,
            today=date.fromisoformat(self.manifest["reviewed_at"]),
            runtime_adapter_id=self.manifest["adapter_id"],
            runtime_schema_version=self.manifest["schema_version"],
            runtime_fingerprint=self.manifest["capability_fingerprint"],
            runtime_provenance_validated=True,
            requested_controls={"imaginary_control": "enabled"},
        )
        self.assertEqual(action, "recommend_only")

    def test_unsupported_control_value_fails_closed(self) -> None:
        action = validate.resolve_adapter_action(
            self.manifest,
            today=date.fromisoformat(self.manifest["reviewed_at"]),
            runtime_adapter_id=self.manifest["adapter_id"],
            runtime_schema_version=self.manifest["schema_version"],
            runtime_fingerprint=self.manifest["capability_fingerprint"],
            runtime_provenance_validated=True,
            requested_controls={"reasoning_effort": "imaginary"},
        )
        self.assertEqual(action, "recommend_only")

    def test_unvalidated_runtime_provenance_fails_closed(self) -> None:
        action = validate.resolve_adapter_action(
            self.manifest,
            today=date.fromisoformat(self.manifest["reviewed_at"]),
            runtime_adapter_id=self.manifest["adapter_id"],
            runtime_schema_version=self.manifest["schema_version"],
            runtime_fingerprint=self.manifest["capability_fingerprint"],
            runtime_provenance_validated=False,
            requested_controls={},
        )
        self.assertEqual(action, "recommend_only")

    def test_mismatched_adapter_id_fails_closed(self) -> None:
        action = validate.resolve_adapter_action(
            self.manifest,
            today=date.fromisoformat(self.manifest["reviewed_at"]),
            runtime_adapter_id="wrong-adapter",
            runtime_schema_version=self.manifest["schema_version"],
            runtime_fingerprint=self.manifest["capability_fingerprint"],
            runtime_provenance_validated=True,
            requested_controls={},
        )
        self.assertEqual(action, "recommend_only")

    def test_mutated_manifest_fingerprint_is_rejected(self) -> None:
        manifest = copy.deepcopy(self.manifest)
        manifest["supported_controls"]["imaginary_control"] = ["enabled"]
        errors = validate.validate_adapter_manifest(manifest, date(2026, 8, 24))
        self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()
