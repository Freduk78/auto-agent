#!/usr/bin/env python3
"""Check repository-local Markdown links without network access."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[2]
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
IGNORED_PREFIXES = ("http://", "https://", "mailto:", "tel:", "#")


def target_exists(source: Path, raw_target: str) -> bool:
    target = raw_target.strip().strip("<>")
    if not target or target.startswith(IGNORED_PREFIXES):
        return True
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc:
        return True
    location = unquote(parsed.path)
    if not location:
        return True
    candidate = (source.parent / location).resolve()
    return candidate == ROOT or ROOT in candidate.parents and candidate.exists()


def main() -> int:
    errors: list[str] = []
    for markdown in sorted(ROOT.rglob("*.md")):
        if ".git" in markdown.parts:
            continue
        text = markdown.read_text(encoding="utf-8")
        for match in LINK.finditer(text):
            if not target_exists(markdown, match.group(1)):
                errors.append(f"{markdown.relative_to(ROOT)}: broken local link {match.group(1)!r}")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("Markdown local links: valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
