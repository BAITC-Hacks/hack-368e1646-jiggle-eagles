# Submission checklist

Confirm the deadline/timezone, required repository/branch, submission channel and deliverables from the current official instructions.

## Functionality and reproducibility

- [ ] Every mandatory [requirement](requirements.md) has passing acceptance evidence for the candidate revision; remaining gaps are explicit.
- [ ] Follow [README](../../README.md) from a clean copy with the Node.js version pinned in [`.nvmrc`](../../.nvmrc), its bundled npm and the root lockfile.
- [ ] Run typecheck, tests, build and the documented launch. Record actual results and skipped checks; verify [CI](../../README.md#continuous-integration) for the final revision when available.
- [ ] Test the main scenario with permitted inputs and independently expected results, including important invalid-input and dependency-failure cases.
- [ ] Document runtime configuration, prerequisites and required data/model access without secret values.

## Documentation and access

- [ ] README describes the submitted version's behavior and limitations. Identify synthetic examples, mocks and unsupported functionality.
- [ ] Update [disclosures](../../DISCLOSURES.md) for reused materials, sources and AI/tool assistance.
- [ ] Check source, frontend assets, logs and evidence for secrets; confirm permitted data and service use.
- [ ] If hosting is required, complete [deployment readiness](deployment-readiness.md) checks and verify reviewer access for the evaluation window.

## Delivery

- [ ] Review the intended diff, preserve unrelated work and record the final commit. Publish only under the team's explicit authorization.
- [ ] Verify the submitted commit is in the required repository and branch. Test deliverable links and reviewer permissions.
- [ ] Include any progress evidence required by the organizers and retain the submission receipt/status where available.
- [ ] Record the submitted revision and time. Follow confirmed freeze rules and demonstrate that version's capabilities.
