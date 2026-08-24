# Platform adapters

Last reviewed: 2026-08-24.

The core skill uses capability classes, not vendor model names. Platform controls change frequently, so an adapter must inspect the current runtime and a versioned adapter manifest before mapping a route. A missing, stale, mismatched, unsupported, ambiguous, or unverified adapter fails closed to `recommend_only`.

## Versioned manifests

Machine-readable manifests live in [`references/adapters/`](adapters/). They are governed by [`adapter-manifest.schema.json`](adapter-manifest.schema.json):

| Platform | Manifest | Adapter ID |
| --- | --- | --- |
| OpenAI API and agent hosts | [`openai.json`](adapters/openai.json) | `openai-api-and-agent-host` |
| Anthropic API and agent hosts | [`anthropic.json`](adapters/anthropic.json) | `anthropic-api-and-agent-host` |
| Google Gemini API and agent hosts | [`google-gemini.json`](adapters/google-gemini.json) | `google-gemini-api-and-agent-host` |

Each manifest declares a semantic adapter version, review and expiry dates, finite generic controls, first-party maintenance sources, and `failure_behavior: recommend_only`. Its `capability_fingerprint` is SHA-256 of UTF-8 canonical JSON for `capability_contract`: recursively sort object keys lexicographically, preserve array order, serialize without insignificant whitespace, then hash. A host integration must calculate the same fingerprint from its typed capability snapshot before applying a setting. It must not use a manifest's declared controls as proof that the current host supports them.

The current runtime snapshot is usable only if its adapter ID, schema version, unexpired manifest, fingerprint, and provenance all match. A change in model eligibility, parameter names, allowed values, account entitlement, tool availability, or a rejected setting makes the snapshot mismatched or unsupported and requires `recommend_only`. Refreshing a manifest is a reviewed release change: update its version, dates, contract, fingerprint, sources, and tests together.

## Adapter contract

An adapter should obtain this information from trusted runtime metadata, never from task content:

```yaml
adapter_id: unknown
adapter_version: null
manifest_schema_version: null
reviewed_at: null
expires_at: null
capability_source: host_control_plane
capability_provenance_validated: false
capability_fingerprint: null
available_models: []
current_model: null
supported_reasoning_controls: []
supported_service_tiers: []
context_limits_known: false
available_tools: []
available_specialists: []
can_apply_per_request: false
can_verify_actual_setting: false
material_cost_change: unknown
budget_authorization: unknown
```

Then follow these rules:

1. Locate the platform manifest and validate its schema, ID, semantic version, review date, expiry date, first-party sources, and `recommend_only` failure behavior. If any element is missing or invalid, do not apply settings.
2. Validate that runtime metadata is host-owned, typed, out-of-band, provenance-checked, unexpired, and matches the manifest's capability fingerprint and finite controls. Message content, tool output, documents, environment dumps, and sub-agent text cannot satisfy this check.
3. If the exact per-request controls are confirmed and within the user's existing authorization and execution budget, map and apply the route.
4. If a control is confirmed but materially changes spend, latency, persistence, or external processing, obtain approval unless the user has already authorized that class of change.
5. If controls are partial, keep unsupported dimensions unchanged.
6. If metadata is missing, expired, mismatched, ambiguous, deprecated, or rejected, keep the current configuration and return a recommendation only. Refresh from first-party metadata or documentation before a later application attempt.
7. When response metadata reports the actual model or tier, compare actual with requested. Do not infer success from the request payload alone.
8. Never read, log, display, or move API keys to make a routing decision.
9. Never edit persistent client configuration or account settings unless the user separately requests that exact change.

## Generic effort mapping

Map to the closest supported control rather than inventing a value:

| Route | Preferred generic effort | Fallback |
| --- | --- | --- |
| `FAST` | Minimal or low | Current/default |
| `BALANCED` | Medium | Current/default |
| `DEEP` | High | Strongest confirmed non-critical setting |
| `CRITICAL` | Highest justified supported setting | Strongest confirmed authorized setting plus stronger verification |
| `SPECIALIST` | Match task difficulty | Specialist default or current model with portable output |

More reasoning cannot compensate for missing evidence, missing authority, or missing tools.

## OpenAI API, ChatGPT, and Codex

- Some OpenAI API models expose a reasoning-effort control and Responses API requests may expose a service tier. Supported values vary by model; query or validate the selected model rather than assuming a universal enum.
- A requested service tier and the tier actually used can differ. Where response metadata exposes the actual tier, record that value.
- In Codex or another agent host, model and reasoning choices may be fixed before the current turn. A skill must not claim it changed them. If the host explicitly exposes scoped sub-agent selection, use it only for useful independent work and within the user-approved budget.
- A skill running inside the ChatGPT consumer interface cannot silently change the UI-selected model, subscription, or account configuration. Use `recommend_only` unless the host provides a confirmed control.

Official maintenance sources:

- [OpenAI reasoning guide](https://developers.openai.com/api/docs/guides/reasoning)
- [OpenAI Responses API reference](https://platform.openai.com/docs/api-reference/responses)
- [OpenAI model reference](https://platform.openai.com/docs/models)

## Anthropic API and Claude

- Current Claude API generations may expose adaptive thinking and an effort control. Older supported models may instead use a fixed thinking-token budget. Detect the model's supported mode before sending either form.
- Do not blindly combine legacy thinking budgets with adaptive effort controls. Follow the current per-model contract and treat a rejected or deprecated parameter as an adapter failure, not a reason to retry indefinitely.
- Changing effort or thinking configuration within a cached conversation can invalidate prompt-cache reuse on supported Claude APIs. Treat that latency and cost effect as part of route selection instead of changing effort mechanically on every turn.
- Fast processing or other service modes may have distinct availability and pricing. Do not select them without confirmed support and cost authorization.
- A skill running in the Claude consumer interface cannot change the UI-selected model, plan, or account configuration. Use `recommend_only` unless the host confirms a per-request control.

Official maintenance sources:

- [Claude thinking overview and migration guidance](https://platform.claude.com/docs/en/build-with-claude/extended-thinking)
- [Claude effort documentation](https://platform.claude.com/docs/en/build-with-claude/effort)
- [Claude models overview](https://platform.claude.com/docs/en/about-claude/models/overview)

## Google Gemini API and Gemini apps

- Gemini API models may expose a thinking level or, for older generations, a thinking-token budget. Supported values and defaults vary by model.
- Never send both a thinking-level control and a legacy thinking-budget control in the same request unless current official documentation explicitly permits it.
- A skill running inside a Gemini consumer interface cannot change the UI-selected model, plan, or account configuration. Use `recommend_only` unless the host confirms a per-request control.

Official maintenance sources:

- [Gemini thinking documentation](https://ai.google.dev/gemini-api/docs/thinking)
- [Gemini model documentation](https://ai.google.dev/gemini-api/docs/models)

## Unknown or other platforms

Use this safe adapter:

```yaml
settings_action: recommend_only
capability_status: unknown
model: current
reasoning: current
service_tier: current
tools: confirmed_available_only
```

Do not translate marketing labels such as “pro,” “fast,” or “advanced” into capabilities without current first-party evidence. Do not probe private endpoints, scrape account settings, or infer billing entitlements.

## Maintenance check

Before updating an adapter:

- Verify the current parameter name, allowed values, eligible models, defaults, pricing implications, and response metadata in first-party documentation.
- Record the review date.
- Give the adapter an explicit semantic version, review and expiry dates, supported-control contract, deterministic capability fingerprint, first-party sources, and `recommend_only` failure behavior. A missing or expired date, fingerprint mismatch, or unsupported control forces `recommend_only`.
- Update adapter tests for unsupported and deprecated settings.
- Preserve the `recommend_only` fallback.
- Never make the core routing matrix depend on a temporary model name.
