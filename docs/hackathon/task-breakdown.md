# Task breakdown

Turn the selected brief into independently verifiable work before implementation. Keep [requirements](requirements.md) and [assignments](agent-assignments.md) as the authoritative records.

## Define the result

Describe one complete scenario: “A user supplies an input; the system processes it and returns a result that supports a decision.” Separate mandatory behavior, supporting work and optional features.

For each requirement, record:

- Source/version/section and a stable ID.
- Observable acceptance steps, expected result and evidence to retain.
- Implementation component, accountable owner and prerequisite decisions.

Include eligibility, functionality, input/output constraints, performance, data handling and required deliverables. Resolve ambiguous clauses before dependent work. Add a UI, model or database only when the required behavior needs it.

## Establish data and interfaces

Inspect provider documentation and sample records for schema, provenance, units, measurement type, intervals/timezone, scope and quality flags. For electricity data, use the [energy index](../energy/README.md) and [validation checklist](../energy/validation-and-guardrails.md#before-analysis). Block calculations with unresolved semantics.

Confirm data access, reuse, redistribution, retention and external-service permissions. Use permitted synthetic fixtures during development and required real inputs for acceptance where applicable.

Agree an API, function or CLI contract with the integrator and affected owners: inputs/outputs, required fields, limits, units/time semantics, validation/errors and a representative acceptance fixture. Record exact file ownership and dependency changes before parallel implementation.

Verify the first implementation performs actual required processing. Label placeholders and mocks, assign their replacement, and exclude them from completed mandatory behavior. Continue with the [execution plan](execution-plan.md).
