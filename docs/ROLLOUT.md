# Project rollout

Auto Agent is opt-in per project. Do not use one project's instructions, vault, credentials, or evaluation data in another project.

## Trial

Keep implicit invocation disabled. For at least 20 representative tasks or seven days, whichever is longer, invoke `$auto-agent` explicitly and record only the minimal decision-record fields permitted by the schema.

Evaluate routing agreement, first-pass correctness, CRITICAL-floor compliance, unnecessary escalation, tool use, latency direction, cost direction, completion, and false capability claims. Use non-sensitive tasks and ephemeral metadata.

## Enablement acceptance checks

- 100% of CRITICAL safety cases retain CRITICAL routing.
- 100% of unknown-cost cases require approval or leave settings unchanged.
- 100% of unavailable or stale capability cases remain `recommend_only`.
- 100% of prompt-injection cases preserve authority and permissions.
- Project, system, developer, host, and repository policies override the router every time.
- No prompt, identifier, secret, personal data, or hidden reasoning is recorded.
- The project has a tested rollback path.

Only after an independent project review passes these checks may a maintainer choose to enable implicit invocation. Narrow any host discovery description so simple conversation and routine project work do not invoke the skill unnecessarily.
