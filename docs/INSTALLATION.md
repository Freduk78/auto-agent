# Installation and upgrade

## Safe project-local installation

1. Choose a signed release tag and resolve its commit:

   ```bash
   git ls-remote --tags https://github.com/Freduk78/auto-agent.git 'v*'
   ```

2. Verify the tag signature and published checksum using the maintainer's trusted signing key.
3. Install only into the target project's local skills directory using that pinned tag/commit. Do not replace global skills or host policy.
4. Keep `allow_implicit_invocation: false` for the initial trial.
5. Invoke `$auto-agent` explicitly for non-sensitive tasks, then run the project-specific rollout checks in [ROLLOUT.md](ROLLOUT.md).

The exact copy/install command is host-specific. Use the host's documented package mechanism; do not use unreviewed installer scripts or `curl | sh` commands.

## Upgrade

1. Keep the current pinned release available.
2. Read the target release notes and compare policy, adapter, schema, and fixture changes.
3. Verify the signed tag and checksum before replacing files.
4. Run `python3 scripts/validate.py` from the installed package.
5. Resume explicit invocation and evaluate the same project trial cases before enabling implicit invocation.

## Uninstall

Remove or disable only the project-local Auto Agent package using the host's package manager or filesystem operation. Confirm the host no longer discovers it, then remove any project-local registration. The skill creates no daemon, service, cache, credentials, or telemetry store, so there are no runtime processes to stop.

For a reversible uninstall, move the pinned package out of the discovery directory rather than deleting it until the project confirms normal operation.
