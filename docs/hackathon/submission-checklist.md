# Money Graph submission checklist

Confirm the current deadline, required repository/branch and submission mechanism with the organizers. This checklist follows [requirements](requirements.md); checking starter connectivity alone does not satisfy task acceptance.

## Required result

- [ ] One documented local command processes raw Parquet and creates all three CSVs in <300 seconds on the official dataset (MG-01).
- [ ] `nodes_roles.csv` has exactly one row for every input gid, including isolates; all roles, scores, cluster references and evidence are valid (MG-02).
- [ ] Every role has documented metrics/thresholds and three arbitrary gids can be explained from those rules (MG-03).
- [ ] `clusters.csv` reports membership counts, seed counts, internal KZT turnover, leading gids and supported hypotheses (MG-04).
- [ ] `top_nodes.csv` ranks at least 20 distinct nodes with consistent scores and evidence (MG-05).
- [ ] Viewer shows directed links, roles and clusters; searching any supplied gid reveals its neighborhood and explanation (MG-06).
- [ ] Outputs account for the four-hop boundary, incomplete incoming flows and 5,000 KZT threshold; all conclusions remain hypotheses with no invented attributes (MG-07).
- [ ] All three files use the fixed [CSV schemas](requirements.md#required-csv-schemas).

## Reproducibility and documentation

- [ ] Clean-machine setup succeeds using the pinned Node version via `nvm use` and all documented pipeline dependencies; raw data access is permitted and documented (MG-08).
- [ ] Core run succeeds offline without paid services or GPU training; repeated outputs and runtime evidence are retained.
- [ ] README includes the actual command, role and priority formulas/thresholds, output examples, limitations and scaling to about one million nodes.
- [ ] [Architecture diagram](../money-graph/architecture.md) reflects the final implementation (MG-09).
- [ ] Root typecheck/tests/build pass; the automated main browser journey passes; final CI is checked or explicitly recorded as unavailable (ENG-01–ENG-02).
- [ ] [Disclosures](../../DISCLOSURES.md) cover actual sources, reused starter code, dependencies and AI assistance. No data, keys or unsupported claims enter the repository or images.

## Five-minute demo

Proposed rehearsal; MG-10 remains unverified until performed. The live pipeline must fit this sequence, so aim comfortably below the five-minute maximum.

| Time | Demonstrate |
| --- | --- |
| 0:00–0:30 | Analyst question, input provenance and collection limits; start the local pipeline |
| 0:30–1:15 | Actual run progress/completion and elapsed time; show the three generated CSVs and node coverage |
| 1:15–2:00 | Network directions, role legend and cluster structure |
| 2:00–3:30 | Search and explain 2–3 nodes from computed metrics, including a fourth-hop or isolated example |
| 3:30–4:30 | Top ≥20 ranking, reasons for priority and questions for further investigation |
| 4:30–5:00 | Reproduction command, limitations and optional next steps |

## Delivery

- [ ] Captain confirms formal task selection, eligibility, organizer repository identity, progress-report requirements and reviewer data access.
- [ ] Rehearse the complete live demo within five minutes; present actual outputs from the demonstrated revision.
- [ ] Review working/staged diffs separately, preserve unrelated work and record the submitted revision. Push or submit only with explicit authorization.
- [ ] Verify repository/artifact links and reviewer permissions; retain submission status before the confirmed cutoff.
