# Money Graph domain guide

The project supports a bank AML analyst investigating a sampled transaction network. Roles describe observed financial patterns and priorities direct human review; neither establishes wrongdoing.

Read the [confirmed requirements](../hackathon/requirements.md) and [source data contract](../hackathon/data-profile.md) before calculations. Source documentation is authoritative for column semantics; this guide defines project guardrails, not additional dataset facts.

- [Methodology](methodology.md): role vocabulary, evidence design, confidence, ranking and collection limits.
- [Proposed architecture](architecture.md): local pipeline, exports, viewer and optional assistant.
- [Acceptance and delivery](../hackathon/submission-checklist.md): all-node coverage, fixed CSVs, timing and demo.

The official input has no role ground truth. Evaluate deterministic behavior, mathematical correctness, explainability, coverage, robustness and practical usefulness; do not claim supervised accuracy or calibrated probabilities from this dataset.
