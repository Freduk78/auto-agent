#!/usr/bin/env python3
"""Generate or verify Auto Agent's deterministic protected-artifact manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Iterable
from pathlib import Path, PurePosixPath

MANIFEST_VERSION = "1.0.0"
CANONICALIZATION = "sorted-path-utf8-nul-raw-file-sha256-lf"


class ManifestError(ValueError):
    """Raised when protected artifact paths or manifest data are unsafe."""


def canonical_json_bytes(value: object) -> bytes:
    """Return deterministic UTF-8 JSON bytes without insignificant whitespace."""

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _safe_relative_path(root: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or not pure.parts or ".." in pure.parts:
        raise ManifestError(f"unsafe protected artifact path: {relative!r}")
    normalized = pure.as_posix()
    if normalized != relative or normalized.startswith("./"):
        raise ManifestError(f"non-canonical protected artifact path: {relative!r}")

    root_resolved = root.resolve()
    candidate = root / Path(*pure.parts)
    if candidate.is_symlink():
        raise ManifestError(f"protected artifact cannot be a symlink: {relative}")
    try:
        candidate.resolve().relative_to(root_resolved)
    except ValueError as exc:
        raise ManifestError(f"protected artifact escapes package root: {relative}") from exc
    if not candidate.is_file():
        raise ManifestError(f"protected artifact is missing: {relative}")
    return candidate


def compute_manifest(root: Path, relative_paths: Iterable[str]) -> dict:
    """Hash a sorted, unique set of package-relative files."""

    paths = list(relative_paths)
    if paths != sorted(paths):
        raise ManifestError("protected artifact paths must be sorted")
    if len(paths) != len(set(paths)):
        raise ManifestError("protected artifact paths must be unique")

    bundle = hashlib.sha256()
    entries: list[dict[str, str]] = []
    for relative in paths:
        path = _safe_relative_path(root, relative)
        file_digest = hashlib.sha256(path.read_bytes()).digest()
        entries.append({"path": relative, "sha256": file_digest.hex()})
        bundle.update(relative.encode("utf-8"))
        bundle.update(b"\0")
        bundle.update(file_digest)
        bundle.update(b"\n")

    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "algorithm": "sha256",
        "canonicalization": CANONICALIZATION,
        "files": entries,
        "bundle_sha256": bundle.hexdigest(),
    }
    manifest["manifest_sha256"] = hashlib.sha256(canonical_json_bytes(manifest)).hexdigest()
    return manifest


def load_protected_paths(root: Path) -> list[str]:
    policy_path = root / "contracts" / "v1" / "policy-rules.json"
    try:
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError(f"cannot load protected artifact policy: {exc}") from exc
    paths = policy.get("protected_artifacts")
    if not isinstance(paths, list) or not all(isinstance(item, str) for item in paths):
        raise ManifestError("protected_artifacts must be an array of strings")
    return paths


def manifest_without_digest(manifest: dict) -> dict:
    value = dict(manifest)
    value.pop("manifest_sha256", None)
    return value


def verify_manifest(root: Path, manifest: dict) -> list[str]:
    """Return deterministic validation errors for a stored manifest."""

    errors: list[str] = []
    if not isinstance(manifest, dict):
        return ["artifact manifest must be an object"]
    entries = manifest.get("files")
    if not isinstance(entries, list):
        return ["artifact manifest files must be an array"]
    paths: list[str] = []
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict) or set(entry) != {"path", "sha256"}:
            errors.append(f"artifact manifest entry {index} is malformed")
            continue
        if not isinstance(entry["path"], str):
            errors.append(f"artifact manifest entry {index} path must be a string")
            continue
        paths.append(entry["path"])
        if not isinstance(entry["sha256"], str) or len(entry["sha256"]) != 64:
            errors.append(f"artifact manifest entry {index} sha256 is invalid")
    if errors:
        return errors

    try:
        required_paths = load_protected_paths(root)
        if paths != required_paths:
            errors.append("artifact manifest protected paths do not match policy")
        expected = compute_manifest(root, required_paths)
    except ManifestError as exc:
        return [str(exc)]

    for key in (
        "manifest_version",
        "algorithm",
        "canonicalization",
        "files",
        "bundle_sha256",
        "manifest_sha256",
    ):
        if manifest.get(key) != expected.get(key):
            label = "artifact bundle digest" if key == "bundle_sha256" else key
            errors.append(f"{label} does not match protected files")
    return errors


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true", help="write references/artifact-manifest.json")
    group.add_argument("--check", action="store_true", help="verify the stored manifest")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    manifest_path = root / "references" / "artifact-manifest.json"
    if args.write:
        try:
            manifest = compute_manifest(root, load_protected_paths(root))
        except ManifestError as exc:
            print(f"ARTIFACT MANIFEST: FAIL\n- {exc}")
            return 1
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        print(f"ARTIFACT MANIFEST: WROTE {manifest['bundle_sha256']}")
        return 0

    try:
        stored = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ARTIFACT MANIFEST: FAIL\n- {exc}")
        return 1
    errors = verify_manifest(root, stored)
    if errors:
        print("ARTIFACT MANIFEST: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"ARTIFACT MANIFEST: PASS {stored['bundle_sha256']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
