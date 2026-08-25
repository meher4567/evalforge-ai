# Release checklist

1. Confirm CI, CodeQL, dependency audits, backend coverage, frontend tests, E2E, and Docker smoke
   all pass from a clean checkout.
2. Run the default staged load test and attach CSV/HTML output to the release issue.
3. Complete a checksum-verified backup/restore drill and record observed RPO/RTO evidence.
4. Validate `render.yaml`, deploy a preview frontend, and run authentication, tenant-isolation,
   evaluation, comparison, readiness, and metrics smoke tests.
5. Confirm `main` requires pull requests, at least one approval, conversation resolution, strict
   status checks, no force pushes, and no deletion.
6. Update `CHANGELOG.md`, version metadata, migration notes, known limitations, and screenshots.
7. Create and push an annotated `v0.1.0` tag only after the release commit is merged to `main`.
8. Verify the generated release archives and `SHA256SUMS`, then monitor SLOs during rollout.

Never tag a release from an unreviewed feature branch or while migrations, restore verification, or
tenant-isolation checks are failing.
