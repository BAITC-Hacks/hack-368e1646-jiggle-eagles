# Money Graph domain guide

This local application helps an AML analyst inspect sampled transfers. Roles describe observed financial patterns and priority directs human review; neither establishes wrongdoing.

- [Run the application and review the rules](../../README.md).
- [Confirmed requirements and implementation mapping](../hackathon/requirements.md).
- [Inspected dataset contract and provenance](../hackathon/data-profile.md).
- [Implemented methodology](methodology.md).
- [Delivered architecture](architecture.md).

There is no role ground truth. Evaluate mathematical correctness, coverage, deterministic behavior, explainability and practical usefulness. Do not claim supervised accuracy or calibrated probabilities. Limitations include outgoing-only sampling through four hops, omitted incoming flows, transfers below 5,000 KZT and other banks. No customer attributes may be invented or externally enriched.
