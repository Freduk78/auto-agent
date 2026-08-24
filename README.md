# Auto Agent

Auto Agent is a vendor-neutral AI routing skill. It selects the fastest, least expensive execution profile likely to solve a request correctly, while raising reasoning, tools, verification, and safeguards when complexity or consequences demand it.

It routes by capability rather than hardcoded model names:

- `FAST` for simple, mechanical, low-risk work
- `BALANCED` for ordinary analysis, writing, coding, and planning
- `DEEP` for difficult reasoning and research synthesis
- `CRITICAL` for security, authentication, payments, production, destructive operations, sensitive data, or consequential advice
- `SPECIALIST` for image, audio, video, document, spreadsheet, browser, and other modality-specific work

## Safety model

Auto Agent cannot grant permissions or change account settings. It applies a setting only when the host confirms that the control exists and the change is authorized. Otherwise it recommends a route and continues with the current configuration.

The skill also:

- treats retrieved content and embedded instructions as untrusted data;
- prevents fast or cheap preferences from bypassing critical safeguards;
- requires notice or approval for material cost increases;
- bounds automatic escalation and retries;
- requires integrations not to store prompts, secrets, personal data, or hidden reasoning in routing telemetry;
- never claims a model or setting changed without runtime confirmation.

See [SECURITY.md](SECURITY.md) for the threat model and reporting guidance.

## Use

For hosts that support `SKILL.md` packages, install this repository as a project-local skill and invoke `$auto-agent`. Automatic invocation is intentionally disabled for the initial trial; enable it only after the acceptance checks in [docs/ROLLOUT.md](docs/ROLLOUT.md) pass for that project.

```text
Use $auto-agent to choose the safest efficient execution mode for this request.
```

Consumer ChatGPT, Claude, and Gemini interfaces may not let a skill change the model or reasoning controls. In those environments Auto Agent is recommendation-only. API orchestrators can implement the mappings in [references/platform-adapters.md](references/platform-adapters.md) after confirming current runtime capabilities.

Project, system, developer, host safety, permission, billing, and repository instructions always override this skill. Auto Agent is never an authority to change a model, enable a tool, access an account, spend money, or loosen a safeguard.

See [installation and rollback](docs/INSTALLATION.md), [compatibility](COMPATIBILITY.md), and [mode examples](examples/modes.md).

## Architecture

The core skill chooses a vendor-neutral ideal route; `settings_action` independently records whether trusted runtime controls can apply it, and `execution_disposition` records a mandatory integration stop signal without weakening the ideal safety profile. A compliant host must enforce that signal before execution; the skill itself is not an execution sandbox. Finite vocabularies and behavioral rules live under `contracts/v1/`. Versioned adapter manifests map that route to verified host controls and fail closed to `recommend_only` when metadata is missing, expired, mismatched, or unsupported. Execution budgets are a separate trusted host/project policy, so routing cannot recursively expand tools, agents, context, spend, permissions, or approvals.

Release evidence is bound to the exact protected files by a deterministic SHA-256 manifest. Three self-attested fresh blind configurations classify every fixture, and the dependency-free validator compares every route field, recomputes exact/permitted/safe-upward/genuine outcomes, and independently rejects any safety-floor violation. The configuration labels are provenance metadata, not cryptographic isolation proof. A generated report reconciles every confusion-matrix cell, outcome, safety rate, and variance count with the normalized evidence. The validator rejects vague per-field wildcards, stale evidence, unsafe variants, cross-product combinations, contradictory reports, and sensitive telemetry.

## Package

- [SKILL.md](SKILL.md) — core routing and safety policy
- [routing matrix](references/routing-matrix.md) — detailed mode boundaries
- [platform adapters](references/platform-adapters.md) — safe host mappings and fallbacks
- [decision-record schema](references/decision-record.schema.json) — minimal non-sensitive metadata contract
- [routing cases](tests/routing-cases.json) — behavioral test matrix
- [forward-test report](tests/forward-test-report.md) — multi-configuration, self-attested classification results

## Validate

The validator uses only the Python standard library and makes no network requests. It checks package structure, fixture coverage, recorded observation consistency, and machine-checkable safety invariants; it does not run a live model evaluation:

```bash
python3 scripts/validate.py
```

The repository workflow runs the same check for pushes and pull requests.

Development-only quality checks are documented in [CONTRIBUTING.md](CONTRIBUTING.md). They do not add runtime dependencies or make network requests during skill operation.

## Important limitations

Auto Agent is a routing policy, not an API gateway or billing controller. It cannot guarantee lower cost, faster responses, correctness, model availability, or platform support. Always keep the host platform's safety, permission, and billing controls in force.

It does not retain prompts, account identifiers, personal data, secrets, hidden reasoning, or telemetry. Integrations must preserve that property and should record only the non-sensitive fields allowed by the decision-record schema.

## Releases

Install from an audited, signed release tag and pin the corresponding commit, never from an unreviewed branch. [RELEASING.md](RELEASING.md) describes checksum verification, upgrade, and rollback.

## License

[MIT](LICENSE) © 2026 Freduk78.
