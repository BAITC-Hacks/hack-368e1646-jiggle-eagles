# Money Graph requirements and verification

## Sources and status

Selected task: **Money Graph — HackAlem AI**, Finance track, task owner Freedom. Official title: «Граф денег: восстановление финансовой структуры организованной группы по транзакционной сети».

- **U:** task summary and project-switch instruction supplied by the user on September 23, 2026.
- **S:** [Full technical specification](https://docs.google.com/document/d/1JPLU-G6R25Ge2hVaY2J9cqvrx7FGExj87XKwJPaMz3o/edit?usp=sharing), Russian sections 1–10 and scoring table, read September 23, 2026 through its text export.
- **D:** [Dataset README](https://drive.google.com/file/d/1ro-SiY042jv7De0h7tXBDyY8ZKdHz_US/view?usp=sharing), read September 23, 2026. It defines source columns and collection scope; actual Parquet files remain uninspected.
- **A:** [Repository agreement](../../AGENTS.md), engineering requirements rather than organizer scoring criteria.

The app currently implements health/echo connectivity. No graph-analysis requirement is verified. Codex is the integrator and acceptance/testing owner; exact ownership is in [assignments](agent-assignments.md). The user/team captain owns registration, current event rules, submission and reviewer data access. Source documents have no pinned version identifier here.

## Mandatory behavior and deliverables

Acceptance procedures below operationalize U/S; they are not additional organizer clauses. Component names are planned responsibilities. Fill in actual paths, revision and evidence as implementation proceeds.

| ID | Source and requirement | Acceptance check | Planned component / status |
| --- | --- | --- | --- |
| MG-01 | U; S §§5, 7, 9: one reproducible local run from raw Parquet to three exports, under five minutes on the supplied data. | From a clean setup, run the documented command with local inputs and no network/AI credentials; time parsing through final CSV writes, require <300 seconds and retain hardware, versions, input hashes, configuration and timing. Repeat with identical inputs/configuration and compare deterministic outputs. | Local pipeline; not implemented |
| MG-02 | U; S §§5, 7: every node has a role, confidence, cluster, priority and explanation. | Exact input/output `gid` set equality, 2,248 rows on the confirmed official input, one row per node including isolates; permitted role, finite scores in [0,1], valid cluster reference, nonempty evidence of at most 200 characters. | Role assignment/export; not implemented |
| MG-03 | U; S §7: role criteria are formal and explainable. | Document every rule, metric, threshold, overlap/tie rule and score interpretation. For three arbitrary gids, explain assignments from computed evidence within one minute. Test motifs with independently expected metrics and counterexamples. | Rules/evidence; not implemented |
| MG-04 | U; S §§5, 7: group nodes into clusters and describe their structure. | Every node belongs to a reported cluster; verify `n_nodes`, `n_seed`, internal transfer sums, member references and a supported structural hypothesis; include isolates and disconnected components. Record algorithm, parameters and random seed if used. | Clustering/export; not implemented |
| MG-05 | U; S §§5, 7: rank at least 20 priority nodes with explanations. | At least 20 distinct valid gids, contiguous ranks, documented deterministic tie handling, descending priorities in [0,1], roles/scores matching node export, nonempty `why` supported by computed features. | Ranking/export; not implemented |
| MG-06 | U; S §§5, 7: show network directions, roles, clusters and search by gid. | On real frontend/backend, search an arbitrary valid gid, inspect incoming/outgoing links, role, cluster and evidence; verify direction/legend and useful missing-ID behavior. Include isolated and boundary nodes. | Graph view/API; not implemented |
| MG-07 | U; S §§6, 9: cautious hypotheses, source-only attributes and collection limits. | Explanations avoid accusations; no external enrichment or invented identity/balance fields. A fourth-hop node with no outgoing edges must not be called a confirmed terminal solely for that absence. Surface the 5,000 KZT threshold, incomplete incoming flows and intra-bank scope. | Validation, scoring and UI; not implemented |
| MG-08 | U; S §§9–10: repository and README explaining one-command reproduction, rules, outputs, limitations and scaling to about one million nodes. | Independent clean-machine rehearsal produces all exports without paid services, cloud cluster or GPU training. README matches delivered behavior and contains a scaling discussion, data-access steps and dependency provenance. No hardcoded gid answer lists. | README/setup; preparation only, reproduction missing |
| MG-09 | U; S §10: architecture diagram. | Diagram accurately traces delivered data → metrics → roles → interface/exports and identifies optional AI boundaries. | [Proposed diagram](../money-graph/architecture.md); final implementation review pending |
| MG-10 | U; S §10: five-minute live demonstration. | Rehearse a live pipeline run, exports, search and substantive explanation of 2–3 nodes within five minutes, including one collection-limit example. | [Demo plan](submission-checklist.md#five-minute-demo); not rehearsed |
| ENG-01 | A: automated browser test of the main user journey. | Implement and run against real frontend/backend, replacing only external services where necessary; cover MG-06 and API/error behavior. | Verification gap: no browser runner or graph journey |
| ENG-02 | A: integrated typecheck, tests, build, diff review and final CI. | Use `nvm use` from the repository root, run root checks and verify CI for the final revision. Separate starter checks from graph acceptance. | [Verification record](integration-verification.md); final CI pending |

## Required CSV schemas

These headers come from S §5. Do not replace them with a custom export contract. Serialization details not defined by the source must be documented before implementation.

| File | Columns in source order | Source constraints |
| --- | --- | --- |
| `nodes_roles.csv` | `gid,role,role_score,cluster_id,priority_score,evidence` | `gid` int64; role string; `role_score` and `priority_score` floats in [0,1]; cluster integer; human-readable `evidence` at most 200 characters; one row per node |
| `clusters.csv` | `cluster_id,n_nodes,n_seed,sum_kzt_internal,top_gids,hypothesis` | One row per cluster; member/seed counts, internal turnover in KZT, leading gids and purpose/structure hypothesis |
| `top_nodes.csv` | `rank,gid,role,priority_score,why` | Ranked list of at least 20 distinct nodes with text justification |

Minimum role dictionary: `consolidator`, `transit`, `distributor`, `terminal`, `coordinator`, `peripheral`. Any extension must be documented. Role confidence is distinct from investigation priority; without labeled roles neither is a measured probability of wrongdoing or calibrated accuracy.

## Evaluation

| Criterion | Points |
| --- | --- |
| Task completion and functionality | 25 |
| Technical implementation | 25 |
| README and reproducibility | 25 |
| Practical value | 15 |
| Originality and development potential | 10 |

## Open implementation decisions

- Inspect and hash the actual archive and organizer starter; verify source counts, dtypes, identifiers, dates, duplicates, isolated nodes and aggregate consistency. Source-reported component counts need reconciliation; see [data contract](data-profile.md).
- Choose a local Parquet reader and graph algorithms after inspecting the starter. Record exact versions, licenses, deterministic behavior and resource costs before adding dependencies.
- Define role thresholds, ambiguous-role handling, confidence, priority contributions, clustering parameters and ranking tie rules. No numeric role thresholds have been adopted yet.
- Define money precision/tolerance from real values; preserve int64 gids losslessly. Define CSV encoding and `top_gids` serialization. The source supplies dates, not timestamps: do not invent intraday order or timezone.
- Confirm data packaging/access for reviewers and current organizer deadline/submission rules using the [resource list](orientation.md). No archive redistribution permission or hosting requirement is inferred.

Optional features include graph-grounded AI questions, temporal patterns, cycles, repeated routes, sensitivity analysis and node-removal analysis. None may become a prerequisite for the local core. Accounting for collection limits remains required by U even though S §8 also lists enhanced boundary handling as an optional extension.
