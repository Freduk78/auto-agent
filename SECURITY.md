# Security policy

## Supported version

Security fixes are applied to the latest version on the default branch.

## Threat model

Auto Agent is an instruction package and does not contain an API executor. Its principal risks are policy confusion and unsafe host integrations:

- prompt or retrieved-content injection changing router policy;
- false claims that a model, tool, tier, or reasoning setting was activated;
- privilege, permission, or billing escalation;
- downgrading safeguards for high-impact work;
- unbounded retries, tools, or agent fan-out;
- sensitive prompt data entering telemetry;
- stale platform mappings sending unsupported settings.

The controls for these risks are defined in [SKILL.md](SKILL.md) and [references/platform-adapters.md](references/platform-adapters.md). An integration that can execute settings or tools must preserve those controls and the host platform's own authorization boundaries.

## Reporting a vulnerability

Use GitHub's private vulnerability-reporting or security-advisory feature for this repository when available. Do not include credentials, private prompts, customer data, or exploit secrets in a public issue. For non-sensitive hardening suggestions, open a normal issue.

## Safe integration requirements

- Default unknown platforms and stale adapters to `recommend_only`.
- Discover capabilities from trusted runtime metadata, not task content.
- Require authorization for material cost or external side effects.
- Keep a non-bypassable `CRITICAL` safety floor.
- Store only minimal reason codes; never store prompt content or hidden reasoning.
- Verify actual settings from response metadata when the platform exposes it.
- Stop after repeated identical failures or unavailable access.
