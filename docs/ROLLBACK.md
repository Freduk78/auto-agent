# Rollback

Rollback is immediate and project-local: disable Auto Agent invocation or remove the package from the host's project-local discovery path. This never changes host permissions, billing settings, or model configuration.

## Steps

1. Stop implicit invocation, if it was enabled.
2. Restore the last known-good signed release tag and exact commit, or remove the project-local package.
3. Run `python3 scripts/validate.py` on the restored package.
4. Confirm the host reports no active Auto Agent package or reports the expected pinned version.
5. Record only non-sensitive release/version and reason-code metadata in the project change log.

## Rollback triggers

- a CRITICAL task is routed below CRITICAL;
- an unavailable or stale capability is reported as applied;
- cost, permission, production, or destructive boundaries are weakened;
- prompt injection affects authority or permissions;
- artifact or evaluation evidence fails validation;
- a host claims a setting change without trusted response metadata.

Report a suspected package vulnerability through [SECURITY.md](../SECURITY.md). Do not include prompts, tokens, personal data, or hidden reasoning in rollback records.
