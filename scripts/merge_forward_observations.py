#!/usr/bin/env python3
"""Merge redacted blind routing outputs into normalized forward-test evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import validate
from artifact_manifest import ManifestError, verify_manifest

RAW_KEYS = {"id"} | validate.EXPECTED_ROUTE_KEYS
HOST_CLASSES = {"codex_subagent", "offline_fixture_evaluator"}
MODEL_CLASSES = {"economy", "balanced", "frontier"}


class MergeError(ValueError):
    """Raised when blind evidence is unsafe, incomplete, or inconsistent."""


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MergeError(f"cannot read {path}: {exc}") from exc


def _safe_raw_path(root: Path, supplied: Path) -> Path:
    path = supplied if supplied.is_absolute() else root / supplied
    path = path.resolve()
    tests_root = (root / "tests").resolve()
    if not path.is_relative_to(tests_root) or not path.name.startswith(".blind-") or path.suffix != ".json":
        raise MergeError("blind input must be a tests/.blind-*.json file")
    return path


def merge_observations(root: Path, evaluations: list[tuple[str, str, str, Path]]) -> dict:
    """Validate redacted raw routes, compute outcomes, and return normalized evidence."""

    root = root.resolve()
    cases_document = _read_json(root / "tests" / "routing-cases.json")
    policy = _read_json(root / "contracts" / "v1" / "policy-rules.json")
    vocabulary = _read_json(root / "contracts" / "v1" / "vocabulary.json")
    profiles = _read_json(root / "tests" / "capability-profiles.json")
    manifest = _read_json(root / "references" / "artifact-manifest.json")
    try:
        manifest_errors = verify_manifest(root, manifest)
    except ManifestError as exc:
        raise MergeError(str(exc)) from exc
    if manifest_errors:
        raise MergeError("artifact manifest is stale: " + "; ".join(manifest_errors))

    errors: list[str] = []
    profile_ids = validate.validate_capability_profiles(profiles, vocabulary, errors)
    cases = validate.validate_cases(cases_document, vocabulary, policy, profile_ids, errors)
    if errors:
        raise MergeError("fixture validation failed: " + "; ".join(errors))
    required_runs = policy.get("required_runs_per_case")
    if len(evaluations) != required_runs:
        raise MergeError(f"exactly {required_runs} blind evaluations are required")

    configurations: list[dict[str, str]] = []
    raw_by_config: list[tuple[str, list[dict]]] = []
    config_ids: set[str] = set()
    config_pairs: set[tuple[str, str]] = set()
    raw_paths: set[Path] = set()
    expected_ids = list(cases)
    for config_id, host_class, model_class, supplied_path in evaluations:
        if (
            not validate.SAFE_ID.fullmatch(config_id)
            or config_id in config_ids
            or host_class not in HOST_CLASSES
            or model_class not in MODEL_CLASSES
        ):
            raise MergeError(f"invalid or duplicate evaluator configuration: {config_id!r}")
        config_ids.add(config_id)
        config_pairs.add((host_class, model_class))
        configurations.append(
            {
                "id": config_id,
                "host_class": host_class,
                "model_class": model_class,
                "isolation": "fresh_context_blind_to_expected",
            }
        )
        raw_path = _safe_raw_path(root, supplied_path)
        if raw_path in raw_paths:
            raise MergeError("each evaluator configuration requires a unique blind input path")
        raw_paths.add(raw_path)
        raw = _read_json(raw_path)
        if not isinstance(raw, list) or len(raw) != len(cases):
            raise MergeError(f"{config_id} must contain exactly {len(cases)} route objects")
        if [item.get("id") for item in raw if isinstance(item, dict)] != expected_ids:
            raise MergeError(f"{config_id} case IDs are incomplete, duplicated, or out of order")
        for item in raw:
            if not isinstance(item, dict) or set(item) != RAW_KEYS:
                raise MergeError(f"{config_id} raw records must contain only finite route metadata")
        raw_by_config.append((config_id, raw))
    minimum = policy.get("minimum_evaluator_configurations", 2)
    if len(config_pairs) < minimum:
        raise MergeError(f"at least {minimum} distinct host/model pairs are required")

    merged = []
    for case_id, case in cases.items():
        runs = []
        for run_number, (config_id, raw) in enumerate(raw_by_config, start=1):
            item = raw[expected_ids.index(case_id)]
            route = {field: item[field] for field in validate.EXPECTED_ROUTE_KEYS}
            route_errors: list[str] = []
            validate.validate_route_values(route, vocabulary, f"{case_id} raw run", route_errors)
            validate.validate_case_semantics(case, route, policy, f"{case_id} raw run", route_errors)
            if route_errors:
                raise MergeError("; ".join(route_errors))
            runs.append(
                {
                    "run": run_number,
                    "evaluator_configuration": config_id,
                    **{field: route[field] for field in validate.ROUTE_FIELDS},
                    "escalation_count": route["escalation_count"],
                    "evaluation_outcome": validate.classify_evaluation_outcome(case, route),
                }
            )
        merged.append({"id": case_id, "runs": runs})

    document = {
        "schema_version": "1.0.0",
        "artifact": {
            "manifest_path": "references/artifact-manifest.json",
            "bundle_sha256": manifest["bundle_sha256"],
            "manifest_sha256": manifest["manifest_sha256"],
        },
        "capability_profile": "fixed_no_controls",
        "runs_per_case": required_runs,
        "evaluator_configurations": configurations,
        "observations": merged,
    }
    observation_errors: list[str] = []
    validate.validate_observations(
        document,
        cases,
        policy,
        vocabulary,
        manifest,
        observation_errors,
    )
    if observation_errors:
        raise MergeError("normalized observation validation failed: " + "; ".join(observation_errors))
    return document


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--evaluation",
        action="append",
        nargs=4,
        metavar=("CONFIG_ID", "HOST_CLASS", "MODEL_CLASS", "RAW_PATH"),
        required=True,
    )
    parser.add_argument("--write", action="store_true", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    evaluations = [
        (config_id, host_class, model_class, Path(raw_path))
        for config_id, host_class, model_class, raw_path in args.evaluation
    ]
    try:
        document = merge_observations(root, evaluations)
    except MergeError as exc:
        print(f"FORWARD OBSERVATION MERGE: FAIL\n- {exc}")
        return 1
    path = root / "tests" / "forward-test-observations.json"
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print(f"FORWARD OBSERVATION MERGE: WROTE {len(document['observations'])} cases")
    return 0


if __name__ == "__main__":
    sys.exit(main())
