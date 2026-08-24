# Releasing Auto Agent

Releases are explicit, reviewable, signed, and reversible. Only a maintainer may create a release.

## Preconditions

1. The working tree is clean and all required CI checks are green.
2. A maintainer independently reviews policy, schema, adapter, workflow, and test changes.
3. The changelog records user-visible and safety-relevant changes.
4. The release version follows Semantic Versioning and has no duplicate tag.

## Release procedure

1. Run the local validator and test suite described in [CONTRIBUTING.md](CONTRIBUTING.md).
2. Create a signed, annotated tag from the audited commit, for example:

   ```bash
   git tag -s v0.1.0 -m 'Auto Agent v0.1.0'
   git verify-tag v0.1.0
   ```

3. Produce a source checksum from that exact commit:

   ```bash
   git archive --format=tar.gz --prefix=auto-agent-v0.1.0/ v0.1.0 > auto-agent-v0.1.0.tar.gz
   shasum -a 256 auto-agent-v0.1.0.tar.gz > SHA256SUMS.txt
   ```

4. Create a GitHub release using the signed tag. Attach the source archive and `SHA256SUMS.txt`; write release notes that link to the changelog and state the tested commit.
5. Verify the public tag signature, release assets, checksums, and CI run after publication.

## Install and upgrade

Pin a project-local installation to both the signed tag and resolved commit. Before upgrading, read the release notes, verify the tag and checksum, run validation, and retain the previous pinned copy for rollback. Detailed steps are in [docs/INSTALLATION.md](docs/INSTALLATION.md).

## Rollback

Disable or remove the project-local skill, restore the previously verified tag/commit, and rerun the validator. Do not use routing to approve actions while a rollback is in progress. See [docs/ROLLBACK.md](docs/ROLLBACK.md).

## Repository settings that must be configured by a maintainer

GitHub branch protection and required checks cannot be enforced by repository files alone. On the default branch, require the GitHub Actions `Quality gate / quality-gate` check (bound to the GitHub Actions app), plus the `Secret scan` workflow; require review; block force-pushes and deletion; and require signed commits or verified signatures where the organization supports them. Restrict GitHub Actions to approved actions and require full-length SHA pinning. These settings must be verified before declaring a release hardened.
