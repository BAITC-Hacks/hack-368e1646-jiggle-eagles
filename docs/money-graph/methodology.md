# Implemented methodology — first local version

The [README rule table and equations](../../README.md#rules-and-scores) are the implemented contract. Code lives in `money_graph/pipeline.py`; synthetic motifs and counterexamples live in `tests/test_money_graph.py`. These are transparent heuristic choices, not learned labels, calibrated probabilities or evidence of wrongdoing.

## Inputs and graph

[Data semantics and provenance](../hackathon/data-profile.md) are confirmed against the downloaded organizer README and actual Parquet files. Preserve exact int64 gids. Build the node universe before payer → recipient edges, retaining all isolates. Validate transaction counts and amounts against the edge aggregate; never add both representations together. Float64 amount reconciliation uses absolute tolerance 0.01 KZT plus relative tolerance 1e-12. Duplicate transaction rows stay because no transaction ID establishes that they are accidental duplicates.

Distinct counterparties exclude the account itself. Self-transfers remain in directed flow/count totals, contribute once to internal cluster turnover, and twice to incident incoming-plus-outgoing activity. This policy is tested; the supplied data has no self-transfers. Dates have day precision and no timezone. Active days and first/last dates are descriptive; there is no claim of sub-day sequencing or traced fund identity.

## Roles and ranking

All qualifying rules compete by base confidence. The README defines thresholds, formulas, tie order, ambiguity deduction and seed/boundary multipliers. Peripheral is a low-confidence fallback. Terminal requires non-seed, depth below four, incoming peers and no outgoing peers, and is still only a possible endpoint of observed flows. A boundary node with several incoming peers can support consolidation but cannot become terminal from absent onward edges.

Priority is the sum of five exposed contributions: incoming peers, outgoing peers, cross-community peers, transaction count and log-normalized observed incident KZT. Role confidence and priority measure different things. Seed membership itself contributes nothing to priority. Ranking uses rounded six-decimal priorities then exact numeric gid. Evidence includes measured counts/amounts and collection caveats; longer explanations show the rule and priority components.

## Communities

Weighted Louvain runs on a sorted undirected projection with reciprocal amounts added, seed 42, resolution 1.0 and threshold 1e-7. Self-links are excluded from community affinity. Isolates become singleton groups. Cluster IDs are assigned by ascending minimum gid. The original directed graph is retained for every flow calculation and display.

Cluster descriptions give member count, internal directed edge count, role composition and boundary count. Member/seed counts, top gids and internal KZT are independently reconciled in acceptance checks. A community is an observed structural grouping, not a proven organization. Pinning versions and insertion order supports repeatability; it does not establish robustness to different algorithms or resolutions.

## Interpretation limits

- All depth-four accounts carry a boundary caveat; none is labeled terminal.
- Incoming flows outside the sample are missing, especially for seeds. Undefined ratios stay undefined; values above one are not clamped. Observed sums are not balances, retained wealth or confirmed fund lineage.
- Only July 2026 intra-bank transfers of at least 5,000 KZT are observed. Smaller transfers and external-bank activity are unknown.
- No invented customer attributes or external enrichment. No model training, application LLM or paid/cloud service participates in reproduction.

Correctness, coverage, deterministic outputs and browser behavior are tested. AML accuracy, threshold sensitivity and partition robustness remain unmeasured without independent investigation or ground truth.
