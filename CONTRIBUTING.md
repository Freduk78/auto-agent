# Contributing

Thank you for helping improve Auto Agent. Changes must keep runtime operation dependency-free, offline, and subordinate to host, system, developer, user, and project policy.

## Scope rules

- Do not add an installer, daemon, network client, credential reader, environment-variable reader, subprocess execution, or dynamic code execution.
- Do not collect prompts, identifiers, personal data, secrets, tool output, or hidden reasoning.
- Unknown, stale, or mismatched capabilities must remain `recommend_only`.
- Cost, permission, production, destructive, security, financial, legal, medical, and sensitive-data safeguards cannot be weakened by user preferences.
- Update fixtures, observations, artifact evidence, and documentation together with any routing-policy change.

## Local checks

The runtime validator requires only Python 3.11+ and the standard library:

```bash
python3 scripts/validate.py
python3 -m unittest discover -s tests -p 'test_*.py'
```

The CI-only analyzers are intentionally separate from runtime. With Python and Ruby available, install the hash-locked analyzer environment, install the checksum-verified Actionlint release described by CI, then run:

```bash
python3 -m pip install --require-hashes -r requirements-dev.lock
ruff check scripts tests .github/scripts
bandit -q -r scripts tests .github/scripts
semgrep scan --config .github/semgrep --error --metrics=off --disable-version-check
actionlint .github/workflows/*.yml
zizmor --offline .github/workflows
python3 .github/scripts/check_markdown_links.py
```

CI installs exact, hash-locked development-tool versions; see [requirements-dev.in](requirements-dev.in), [requirements-dev.lock](requirements-dev.lock), and [quality-gate.yml](.github/workflows/quality-gate.yml). Actionlint's release archive is also verified against a pinned SHA-256 digest. The GitHub-hosted CI bootstrap is development-only and is separately audited by zizmor; it does not change the dependency-free runtime package. Do not replace hashes or immutable action SHAs with mutable tags.

## Pull requests

- Keep changes focused and explain any altered safety invariant.
- Add regression coverage for every validator or policy defect.
- Run applicable checks and report skipped checks with the reason.
- Never commit credentials or copy private prompt/tool data into fixtures.
- Changes to policy, adapters, workflows, schemas, scripts, or tests require maintainer review as declared in [CODEOWNERS](.github/CODEOWNERS).

## Security reports

Follow [SECURITY.md](SECURITY.md); do not open public issues containing sensitive material.
