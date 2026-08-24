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

For hosts that support `SKILL.md` packages, install this repository as a skill and invoke `$auto-agent`. Keep automatic invocation enabled when the host supports it.

```text
Use $auto-agent to choose the safest efficient execution mode for this request.
```

Consumer ChatGPT, Claude, and Gemini interfaces may not let a skill change the model or reasoning controls. In those environments Auto Agent is recommendation-only. API orchestrators can implement the mappings in [references/platform-adapters.md](references/platform-adapters.md) after confirming current runtime capabilities.

## Package

- [SKILL.md](SKILL.md) — core routing and safety policy
- [routing matrix](references/routing-matrix.md) — detailed mode boundaries
- [platform adapters](references/platform-adapters.md) — safe host mappings and fallbacks
- [decision-record schema](references/decision-record.schema.json) — minimal non-sensitive metadata contract
- [routing cases](tests/routing-cases.json) — behavioral test matrix
- [forward-test report](tests/forward-test-report.md) — independent classification results

## Validate

The validator uses only the Python standard library and makes no network requests. It checks package structure, fixture coverage, recorded observation consistency, and machine-checkable safety invariants; it does not run a live model evaluation:

```bash
python3 scripts/validate.py
```

The repository workflow runs the same check for pushes and pull requests.

## Important limitation

Auto Agent is a routing policy, not an API gateway or billing controller. It cannot guarantee lower cost, faster responses, correctness, model availability, or platform support. Always keep the host platform's safety, permission, and billing controls in force.

## License

[MIT](LICENSE) © 2026 Freduk78.
