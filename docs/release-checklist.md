# Release Checklist

This guide captures the steps required to cut a new Unirun release once the
roadmap milestones for the cycle are complete. Follow the order below so the
automated publishing workflow can succeed without manual patches.

## Pre-release validation

1. Confirm `main` is green on the latest commit (`uv run pytest`, `make lint-check`,
   compat contracts, mutation, and benchmark workflows).
2. Update release notes and user-facing docs (`README.md`, `docs/` companions) so
   the new behaviour is discoverable.
3. Regenerate any compatibility snapshots or benchmark artifacts that changed
   during the cycle.
4. Run `uv run pytest` against all supported interpreters locally when possible
   to mirror the CI matrix.

## Cut a release candidate

1. Create a release branch (for example `release/v1.0.0-rc1`) and cherry-pick any
   final fixes needed for the milestone.
2. Tag the branch with an RC tag (`git tag v1.0.0-rc1 && git push origin v1.0.0-rc1`)
   so downstream pipelines can exercise the build.
3. Run the burn-in plan (benchmarks, compat contracts, stress fixtures) against
   the RC tag. Capture findings in the release notes.
4. If regressions appear, fix them on the release branch and repeat the RC tag
   sequence until the checks pass.

## Publish the final release

1. Merge the release branch to `main` once the RC passes burn-in.
2. Tag the commit with the final semantic version (`git tag v1.0.0 &&
   git push origin v1.0.0`). Tags matching `v*` automatically trigger the
   `Publish Package` workflow.
3. The workflow builds distributions via `uvx --python 3.14 hatch build` and publishes them
   to PyPI using trusted publishing (OIDC). Monitor the workflow run and release
   job logs to confirm a successful upload.
4. Draft the GitHub release notes (or promote the latest RC notes) and announce
   availability. Cross-link benchmarks, matrix artifacts, and migration guides.

## Post-release follow-up

1. Bump documentation versions or compatibility tables referencing the just-cut
   release.
2. Reset tracking issues for the next milestone phase and capture any deferred
   tasks.
3. If the release introduced new environment toggles or operational guidance,
   notify downstream consumers and update internal runbooks.
