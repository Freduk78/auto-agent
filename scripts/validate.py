#!/usr/bin/env python3
"""Validate the Auto Agent package without network access or dependencies."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FILES = (
    "SKILL.md",
    "README.md",
    "SECURITY.md",
    "LICENSE",
    "agents/openai.yaml",
    "references/platform-adapters.md",
    "references/routing-matrix.md",
    "references/decision-record.schema.json",
    "tests/routing-cases.json",
    "tests/forward-test-report.md",
    "tests/forward-test-protocol.md",
    "tests/forward-test-observations.json",
)
ALLOWED_MODES = {"FAST", "BALANCED", "DEEP", "CRITICAL", "SPECIALIST"}
ALLOWED_SPECIALIST_ROUTES = {
    "image",
    "audio",
    "video",
    "document",
    "spreadsheet",
    "browser",
    "diagram",
    "security_review",
    "code_execution",
    "other_confirmed",
}
REQUIRED_TAGS = {
    "trivial",
    "creative",
    "coding",
    "research",
    "long_context",
    "security",
    "payment",
    "destructive",
    "ambiguous",
    "explicit_speed",
    "explicit_quality",
    "unavailable_switching",
    "specialist",
    "prompt_injection",
    "unknown_cost",
    "stale_adapter",
    "tool_output",
    "subagent_output",
    "spoofed_metadata",
    "budget",
    "sensitive_data",
}
SENSITIVE_TAGS = {
    "security",
    "authentication",
    "payment",
    "destructive",
    "medical",
    "sensitive_data",
    "critical",
    "production",
}
SECRET_PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "AWS temporary access key": re.compile(r"\bASIA[0-9A-Z]{16}\b"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    "OpenAI-style token": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
    "Anthropic token": re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b"),
    "Google API key": re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"),
    "Stripe secret key": re.compile(r"\b[rs]k_(?:live|test)_[0-9A-Za-z]{16,}\b"),
    "Slack token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    "JWT or bearer token": re.compile(
        r"(?:\bBearer\s+)?eyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{8,}\b"
    ),
    "credential-bearing connection URI": re.compile(
        r"(?i)\b(?:postgres(?:ql)?|mongodb(?:\+srv)?|mysql|redis)://[^:\s/@]+:[^@\s/]+@"
    ),
    "password assignment": re.compile(
        r"(?i)\b(?:password|passwd|pwd)\s*[:=]\s*[\"'][^\"'\n]{8,}[\"']"
    ),
}
MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def validate_required_files(errors: list[str]) -> None:
    for relative in REQUIRED_FILES:
        path = ROOT / relative
        if not path.is_file():
            fail(errors, f"missing required file: {relative}")


def validate_skill(errors: list[str]) -> None:
    path = ROOT / "SKILL.md"
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        fail(errors, "SKILL.md must start with YAML frontmatter")
        return
    parts = text.split("---", 2)
    if len(parts) != 3:
        fail(errors, "SKILL.md frontmatter is malformed")
        return
    frontmatter = parts[1]
    if not re.search(r"^name:\s*auto-agent\s*$", frontmatter, re.MULTILINE):
        fail(errors, "SKILL.md frontmatter name must be auto-agent")
    description = re.search(r"^description:\s*(.+)$", frontmatter, re.MULTILINE)
    if not description or len(description.group(1).strip()) < 40:
        fail(errors, "SKILL.md needs a discriminating description")
    if "TODO" in text or "[TODO" in text:
        fail(errors, "SKILL.md contains unfinished scaffold text")
    for mode in ALLOWED_MODES:
        if f"`{mode}`" not in text:
            fail(errors, f"SKILL.md does not define {mode}")
    for required_phrase in (
        "recommend_only",
        "two automatic escalations",
        "untrusted task data",
        "cannot change account settings",
        "Root-request execution envelope",
        "validated provenance",
    ):
        if required_phrase not in text:
            fail(errors, f"SKILL.md is missing safety invariant: {required_phrase}")


def validate_openai_yaml(errors: list[str]) -> None:
    path = ROOT / "agents/openai.yaml"
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    for expected in (
        'display_name: "Auto Agent"',
        'short_description: "Choose safe AI effort, speed, and tools"',
        'default_prompt: "Use $auto-agent',
        "allow_implicit_invocation: true",
    ):
        if expected not in text:
            fail(errors, f"agents/openai.yaml is missing: {expected}")


def validate_json_files(errors: list[str]) -> tuple[list[dict], dict, dict]:
    cases: list[dict] = []
    schema: dict = {}
    observations: dict = {}
    for relative in (
        "tests/routing-cases.json",
        "references/decision-record.schema.json",
        "tests/forward-test-observations.json",
    ):
        path = ROOT / relative
        if not path.is_file():
            continue
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            fail(errors, f"invalid JSON in {relative}: {exc}")
            continue
        if relative == "tests/routing-cases.json":
            if isinstance(parsed, list):
                cases = parsed
            else:
                fail(errors, "tests/routing-cases.json must contain an array")
        elif relative == "references/decision-record.schema.json":
            if isinstance(parsed, dict):
                schema = parsed
            else:
                fail(errors, "decision-record schema must contain an object")
        elif isinstance(parsed, dict):
            observations = parsed
        else:
            fail(errors, "forward-test observations must contain an object")
    return cases, schema, observations


def validate_cases(errors: list[str], cases: list[dict]) -> None:
    if not isinstance(cases, list):
        fail(errors, "routing cases must be a JSON array")
        return
    if len(cases) < 20:
        fail(errors, f"expected at least 20 routing cases, found {len(cases)}")

    ids: set[str] = set()
    observed_modes: set[str] = set()
    observed_tags: set[str] = set()
    for index, case in enumerate(cases, start=1):
        if not isinstance(case, dict):
            fail(errors, f"case {index} must be an object")
            continue
        missing = {"id", "title", "tags", "prompt", "expected", "assertions"} - set(case)
        if missing:
            fail(errors, f"case {index} missing fields: {sorted(missing)}")
            continue
        case_id = case["id"]
        if not isinstance(case_id, str) or not re.fullmatch(r"T\d{2}", case_id):
            fail(errors, f"case {index} has invalid id: {case_id!r}")
        elif case_id in ids:
            fail(errors, f"duplicate case id: {case_id}")
        else:
            ids.add(case_id)

        if not isinstance(case["title"], str) or not case["title"].strip():
            fail(errors, f"{case_id} title must be a non-empty string")
        if not isinstance(case["prompt"], str) or not case["prompt"].strip():
            fail(errors, f"{case_id} prompt must be a non-empty string")

        tags = case["tags"]
        tag_set: set[str] = set()
        if not isinstance(tags, list) or not tags or not all(isinstance(tag, str) for tag in tags):
            fail(errors, f"{case_id} must have string tags")
        else:
            observed_tags.update(tags)
            tag_set = set(tags)

        expected = case["expected"]
        required_expected = {
            "mode",
            "reasoning",
            "tool_policy",
            "verification",
            "settings_action",
            "approval_required",
        }
        if not isinstance(expected, dict) or required_expected - set(expected):
            fail(errors, f"{case_id} has an incomplete expected route")
        else:
            mode = expected["mode"]
            if mode not in ALLOWED_MODES:
                fail(errors, f"{case_id} has invalid mode: {mode!r}")
            else:
                observed_modes.add(mode)
            if not isinstance(expected["approval_required"], bool):
                fail(errors, f"{case_id} approval_required must be boolean")

            for field in ("reasoning", "tool_policy", "settings_action"):
                value = expected[field]
                if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9_]{2,64}", value):
                    fail(errors, f"{case_id} {field} must use a bounded snake_case value")
            if expected["verification"] not in {"focused", "standard", "deep", "critical", "specialist"}:
                fail(errors, f"{case_id} has invalid verification: {expected['verification']!r}")
            specialist_route = expected.get("specialist_route")
            if specialist_route is not None and specialist_route not in ALLOWED_SPECIALIST_ROUTES:
                fail(errors, f"{case_id} has invalid specialist_route")

            verification = expected["verification"]
            settings_action = expected["settings_action"]
            if mode == "CRITICAL" and verification != "critical":
                fail(errors, f"{case_id} CRITICAL route must use critical verification")
            if mode == "SPECIALIST" and not expected.get("specialist_route"):
                fail(errors, f"{case_id} SPECIALIST route must name specialist_route")
            if settings_action == "approval_required" and expected["approval_required"] is not True:
                fail(errors, f"{case_id} approval action must set approval_required=true")
            if SENSITIVE_TAGS & tag_set and mode != "CRITICAL":
                fail(errors, f"{case_id} sensitive tags require CRITICAL mode")
            if {"unavailable_switching", "stale_adapter"} & tag_set:
                if settings_action != "recommend_only":
                    fail(errors, f"{case_id} unavailable/stale capability must be recommend_only")
            if "unknown_cost" in tag_set:
                if settings_action != "approval_required" or expected["approval_required"] is not True:
                    fail(errors, f"{case_id} unknown material cost must require approval")
            if "prompt_injection" in tag_set and settings_action not in {"unchanged", "recommend_only"}:
                fail(errors, f"{case_id} prompt injection cannot apply settings")
            if "budget" in tag_set and expected.get("agent_policy") != "bounded":
                fail(errors, f"{case_id} budget test must enforce bounded agents")

        assertions = case["assertions"]
        if (
            not isinstance(assertions, list)
            or len(assertions) < 2
            or not all(isinstance(assertion, str) and assertion.strip() for assertion in assertions)
        ):
            fail(errors, f"{case_id} must have at least two assertions")

    missing_modes = ALLOWED_MODES - observed_modes
    if missing_modes:
        fail(errors, f"routing matrix does not cover modes: {sorted(missing_modes)}")
    missing_tags = REQUIRED_TAGS - observed_tags
    if missing_tags:
        fail(errors, f"routing matrix does not cover required tags: {sorted(missing_tags)}")


def validate_schema(errors: list[str], schema: dict) -> None:
    if not schema:
        return
    if not isinstance(schema, dict):
        fail(errors, "decision-record schema must be an object")
        return
    if schema.get("additionalProperties") is not False:
        fail(errors, "decision-record schema must reject additional properties")
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        fail(errors, "decision-record schema properties must be an object")
        return
    modes = set(properties.get("mode", {}).get("enum", []))
    if modes != {mode.lower() for mode in ALLOWED_MODES}:
        fail(errors, "decision-record schema mode enum is incomplete")
    escalation = properties.get("escalation_count", {})
    if escalation.get("maximum") != 2:
        fail(errors, "decision-record schema must cap escalation_count at 2")
    confidence = set(properties.get("route_confidence", {}).get("enum", []))
    if confidence != {"low", "medium", "high"}:
        fail(errors, "decision-record schema route_confidence enum is incomplete")
    reason_codes = properties.get("reason_codes", {})
    if not isinstance(reason_codes, dict):
        fail(errors, "decision-record reason_codes must be an object")
        return
    if reason_codes.get("maxItems") != 8 or "enum" not in reason_codes.get("items", {}):
        fail(errors, "decision-record reason_codes must be finite and capped at 8")
    required_record_fields = {
        "cost_status",
        "budget_authorization",
        "reasoning_effort",
        "latency_preference",
        "context_policy",
        "tool_policy",
        "agent_policy",
        "response_style",
    }
    if required_record_fields - set(schema.get("required", [])):
        fail(errors, "decision-record schema is missing execution or cost fields")
    specialist_routes = set(properties.get("specialist_route", {}).get("enum", []))
    if specialist_routes != ALLOWED_SPECIALIST_ROUTES | {None}:
        fail(errors, "decision-record specialist_route must use the finite generic vocabulary")
    rules = schema.get("allOf", [])
    if not isinstance(rules, list) or len(rules) < 7:
        fail(errors, "decision-record schema is missing conditional safety rules")
    else:
        serialized_rules = json.dumps(rules, sort_keys=True)
        for required_fragment in (
            '"settings_action": {"const": "applied"}',
            '"capability_status": {"const": "confirmed"}',
            '"mode": {"const": "critical"}',
            '"verification": {"const": "critical"}',
            '"specialist_route": {"type": "string"}',
            '"cost_status": {"enum": ["higher", "unknown"]}',
            '"destructive_action"',
            '"sensitive_domain:payments"',
        ):
            if required_fragment not in serialized_rules:
                fail(errors, f"decision-record schema is missing rule fragment: {required_fragment}")
    forbidden_fields = {"prompt", "input", "secret", "reasoning_text", "chain_of_thought"}
    if forbidden_fields & set(properties):
        fail(errors, "decision-record schema contains sensitive fields")


def validate_observations(errors: list[str], cases: list[dict], document: dict) -> int:
    if not document:
        return 0
    for field in ("observed_at", "artifact", "host", "evaluator_model", "limitations"):
        if not isinstance(document.get(field), str) or not document[field].strip():
            fail(errors, f"forward-test observations missing metadata: {field}")
    runs_per_case = document.get("runs_per_case")
    if not isinstance(runs_per_case, int) or runs_per_case < 1:
        fail(errors, "forward-test runs_per_case must be a positive integer")
    controls_exposed = document.get("controls_exposed")
    if not isinstance(controls_exposed, bool):
        fail(errors, "forward-test controls_exposed must be boolean")

    observations = document.get("observations")
    if not isinstance(observations, list):
        fail(errors, "forward-test observations must be an array")
        return 0

    case_by_id = {
        case["id"]: case
        for case in cases
        if isinstance(case, dict) and isinstance(case.get("id"), str) and isinstance(case.get("expected"), dict)
    }
    observed_by_id: dict[str, dict] = {}
    allowed_actions = {"applied", "unchanged", "recommend_only", "approval_required"}
    for index, observation in enumerate(observations, start=1):
        if not isinstance(observation, dict):
            fail(errors, f"observation {index} must be an object")
            continue
        missing = {
            "id",
            "evaluator",
            "observed_mode",
            "settings_action",
            "approval_required",
        } - set(observation)
        if missing:
            fail(errors, f"observation {index} missing fields: {sorted(missing)}")
            continue
        case_id = observation["id"]
        if not isinstance(case_id, str) or not re.fullmatch(r"T\d{2}", case_id):
            fail(errors, f"observation {index} has invalid id")
            continue
        if case_id in observed_by_id:
            fail(errors, f"duplicate observation id: {case_id}")
            continue
        observed_by_id[case_id] = observation
        if not isinstance(observation["evaluator"], str) or not observation["evaluator"].strip():
            fail(errors, f"{case_id} observation evaluator must be a non-empty string")
        if observation["observed_mode"] not in ALLOWED_MODES:
            fail(errors, f"{case_id} observation has invalid mode")
        if observation["settings_action"] not in allowed_actions:
            fail(errors, f"{case_id} observation has invalid settings_action")
        if not isinstance(observation["approval_required"], bool):
            fail(errors, f"{case_id} observation approval_required must be boolean")

        case = case_by_id.get(case_id)
        expected = case.get("expected") if case else None
        tags = set(case.get("tags", [])) if case and isinstance(case.get("tags"), list) else set()
        if expected and observation["observed_mode"] != expected.get("mode"):
            fail(errors, f"{case_id} observed mode does not match expected mode")
        if expected and expected.get("approval_required") is True:
            if observation["approval_required"] is not True:
                fail(errors, f"{case_id} lost required approval in observation")
        action = observation["settings_action"]
        if controls_exposed is False and action == "applied":
            fail(errors, f"{case_id} cannot apply settings when runtime controls were not exposed")
        if expected and expected.get("approval_required") is True and action == "applied":
            fail(errors, f"{case_id} cannot apply settings before required approval")
        untrusted_or_unavailable = {
            "unavailable_switching",
            "stale_adapter",
            "prompt_injection",
            "tool_output",
            "subagent_output",
            "spoofed_metadata",
        }
        if tags & untrusted_or_unavailable and action not in {"unchanged", "recommend_only"}:
            fail(errors, f"{case_id} untrusted or unavailable controls must fail closed")
        if "unknown_cost" in tags:
            if observation["approval_required"] is not True or action == "applied":
                fail(errors, f"{case_id} unknown cost cannot be applied without approval")

    missing_ids = set(case_by_id) - set(observed_by_id)
    extra_ids = set(observed_by_id) - set(case_by_id)
    if missing_ids:
        fail(errors, f"forward-test observations missing cases: {sorted(missing_ids)}")
    if extra_ids:
        fail(errors, f"forward-test observations contain unknown cases: {sorted(extra_ids)}")
    return len(observations)


def validate_local_links(errors: list[str]) -> None:
    for path in ROOT.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        for target in MARKDOWN_LINK.findall(text):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            clean_target = target.split("#", 1)[0]
            if not clean_target:
                continue
            resolved = (path.parent / clean_target).resolve()
            try:
                resolved.relative_to(ROOT.resolve())
            except ValueError:
                fail(errors, f"{path.relative_to(ROOT)} link escapes repository: {target}")
                continue
            if not resolved.exists():
                fail(errors, f"broken local link in {path.relative_to(ROOT)}: {target}")


def validate_secret_hygiene(errors: list[str]) -> None:
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                fail(errors, f"possible {label} in {path.relative_to(ROOT)}")


def main() -> int:
    errors: list[str] = []
    validate_required_files(errors)
    validate_skill(errors)
    validate_openai_yaml(errors)
    cases, schema, observations = validate_json_files(errors)
    validate_cases(errors, cases)
    validate_schema(errors, schema)
    observation_count = validate_observations(errors, cases, observations)
    validate_local_links(errors)
    validate_secret_hygiene(errors)

    if errors:
        print("AUTO AGENT VALIDATION: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print("AUTO AGENT VALIDATION: PASS")
    print(f"- required files: {len(REQUIRED_FILES)}")
    print(f"- routing cases: {len(cases)}")
    print(f"- recorded forward observations: {observation_count}")
    print(f"- covered modes: {', '.join(sorted(ALLOWED_MODES))}")
    print("- safety invariants: present")
    print("- local links: valid")
    print("- known secret patterns: none detected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
