# Money Graph task breakdown

## First complete analyst journey

An analyst runs one local command against the three organizer Parquet files. The pipeline validates the input, builds the directed network, computes documented metrics, assigns roles/clusters/priorities and writes the three required CSVs. The analyst opens the viewer, selects a priority node or searches a gid, inspects its incoming/outgoing links and reads the evidence and collection caveats. They form a shortlist for further investigation; the tool does not determine guilt.

Acceptance: raw data → all-node coverage → reproducible exports → ranked explanations → searchable graph. Validate a seed with no observed edges, a fourth-hop node and an ambiguous role alongside an ordinary node. The planned flow is shown in [architecture](../money-graph/architecture.md).

## Work packages

| Work | Requirement IDs | Dependencies and evidence |
| --- | --- | --- |
| Inspect organizer inputs/starter | MG-01, MG-07 | Confirm [source contract](data-profile.md), hashes, counts and graph completeness; decide runtime/dependencies |
| Local graph pipeline | MG-01, MG-04 | Preserve isolates; compute directed features and stable clusters; independently check synthetic motifs and actual aggregates |
| Role/ranking rules and explanations | MG-02, MG-03, MG-05, MG-07 | Document thresholds, overlap, confidence, priority contributions and boundary handling; no hardcoded gid lists |
| CSV exports and reproducibility | MG-01, MG-02, MG-04, MG-05, MG-08 | Exact schemas, valid ranges/references, deterministic ordering, full-run timing and offline reproduction |
| Viewer and search | MG-06, ENG-01 | Real output/API; arrows, legends, cluster/role filters, gid search and evidence; browser acceptance |
| Documentation and demo | MG-08–MG-10, ENG-02 | Update final diagram, setup/rules/limitations/scaling; integrated checks and five-minute rehearsal |

## Proposed boundaries, not implemented APIs

| Boundary | Input → output | Validation and failure behavior |
| --- | --- | --- |
| Ingestion | Local Parquet files → typed nodes, edges, transactions and quality report | Fail with actionable messages for missing files, invalid types/IDs, dangling references and unreconciled aggregates; no silent substitutions |
| Analysis | Validated graph plus versioned rules → features, role hypotheses, cluster membership and ranking | Reject nonfinite scores; handle zero denominators explicitly; record parameters and deterministic seeds/ties |
| Export | Successful analysis → exact CSV schemas in [requirements](requirements.md) | Write consistent complete files; do not leave partial output presented as a successful run |
| Viewer/API | Local analysis artifact → network, node details, clusters and ranked evidence | Preserve int64 IDs as decimal strings in JSON/UI; validate requests/responses; explicit unknown-gid and missing-output states |
| Optional assistant | Authorized question plus computed graph evidence → cited explanation | Read-only graph functions, validated outputs, no fabricated attributes or numeric calculations in prompts; failure cannot block the core |

Current HTTP routes remain `/api/health` and `/api/echo`. Freeze actual endpoint shapes and exact file ownership with the integrator before feature work. No new package, runtime or graph API is selected by this document. The organizer starter is a candidate input, not integrated code.

## Independent acceptance fixtures

Use clearly synthetic IDs and amounts. Useful motifs include many-to-one, one-to-many, a chain, a cycle, an isolated seed, a fourth-hop leaf and a node whose observed outflow exceeds observed inflow. Check expected degrees and sums by hand. Test that a chain's last collected node is not claimed to retain funds from a zero out-degree alone, and that missing observations are not replaced with zero balances. Exact role expectations depend on the documented rules once chosen.
