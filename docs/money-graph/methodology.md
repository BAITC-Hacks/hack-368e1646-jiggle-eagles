# Implemented methodology — minimal v2

The [README rule table and equations](../../README.md#rules-and-scores) are the implemented contract. Code lives in `money_graph/pipeline.py`; synthetic motifs and counterexamples live in `tests/test_money_graph.py`. These are transparent heuristic choices, not learned labels, calibrated probabilities or evidence of wrongdoing.

## Inputs and graph

[Data semantics and provenance](../hackathon/data-profile.md) are confirmed against the downloaded organizer README and actual Parquet files. Preserve exact int64 gids. Build the node universe before payer → recipient edges, retaining all isolates. Validate transaction counts and amounts against the edge aggregate; never add both representations together. Float64 amount reconciliation uses absolute tolerance 0.01 KZT plus relative tolerance 1e-12. Duplicate transaction rows stay because no transaction ID establishes that they are accidental duplicates.

Distinct counterparties exclude the account itself. Self-transfers remain in directed flow/count totals, contribute once to internal cluster turnover, and twice to incident incoming-plus-outgoing activity. This policy is tested; the supplied data has no self-transfers. Dates have day precision and no timezone. Active days and first/last dates are descriptive; there is no claim of sub-day sequencing or traced fund identity.

## Roles and ranking

All qualifying rules compete by base confidence. The README defines thresholds, formulas, tie order, ambiguity deduction and seed/boundary multipliers. Peripheral is a low-confidence fallback. Terminal requires non-seed, depth below four, incoming peers and no outgoing peers, and is still only a possible endpoint of observed flows. A boundary node with several incoming peers can support consolidation but cannot become terminal from absent onward edges.

Priority is the sum of five exposed contributions: incoming peers, outgoing peers, cross-community peers, transaction count and log-normalized observed incident KZT. Role confidence and priority measure different things. Seed membership itself contributes nothing to priority. Ranking uses rounded six-decimal priorities then exact numeric gid. Evidence includes measured counts/amounts and collection caveats; longer explanations show the rule and priority components.

## Communities

Weighted Louvain runs on a sorted undirected projection with reciprocal amounts added, seed 42, resolution 1.0 and threshold 1e-7. Self-links are excluded from community affinity. Isolates become singleton groups. Cluster IDs are assigned by ascending minimum gid. The original directed graph is retained for every flow calculation and display.

Cluster descriptions give member count, internal directed edge count, role composition and boundary count. They count fan-in candidates (incoming peers ≥3 and ≥2× outgoing), fan-out candidates (outgoing peers ≥5 and ≥2× incoming), and potential bridging accounts with incoming and outgoing peers in different communities. These motifs use all observed peers, not only internal links, and do not depend on which competing role wins. Self-links are excluded from peer counts. Examples maximize the relevant degree or neighbor-community count, breaking ties by exact numeric gid; fan examples report in/out peers and KZT, bridging examples report community and cross-community-peer counts. No matching motif produces an explicit no-pattern statement. Every summary repeats collection caveats. These descriptive counts do not alter community detection, roles, confidence or priority. Member/seed counts, top gids and internal KZT are independently reconciled in acceptance checks. A community is an observed structural grouping, not a proven organization. Pinning versions and insertion order supports repeatability; it does not establish robustness to different algorithms or resolutions.

## Interpretation limits

- All depth-four accounts carry a boundary caveat; none is labeled terminal.
- Incoming flows outside the sample are missing, especially for seeds. Undefined ratios stay undefined; values above one are not clamped. Observed sums are not balances, retained wealth or confirmed fund lineage.
- Only July 2026 intra-bank transfers of at least 5,000 KZT are observed. Smaller transfers and external-bank activity are unknown.
- No invented customer attributes or external enrichment. No model training, application LLM or paid/cloud service participates in reproduction.

Correctness, coverage, deterministic outputs and browser behavior are tested. AML accuracy, threshold sensitivity and partition robustness remain unmeasured without independent investigation or ground truth.

## Exploration and upload publication

Graph distance counts connections in either direction, independently of transfer direction and original collection depth. Breadth-first neighborhoods stop at one or two hops. At most 50 accounts are selected by distance then numeric gid, including the center. Every edge in the induced directed subgraph is displayed, including self/reciprocal links. Eligible and omitted counts make truncation explicit; it never removes accounts from calculations or exports.

Uploads run the same validation, analysis and export pipeline as the CLI, in separate local directories. A complete result snapshot and downloadable CSV/manifest bytes are published together after successful processing. Failed input or runtime errors leave the active snapshot intact. Successful upload inputs and outputs are retained for deterministic reproduction; the original startup output is preserved.


## Temporal allocation (rules version 2)

After validation, group non-self transaction amounts by account, direction and calendar date with `math.fsum`. Process outgoing days ascending. Consume the earliest remaining eligible incoming daily bucket first (FIFO), only when the outgoing date is 1 or 2 calendar days later. Decrement both capacities by the allocated amount. Expired incoming amounts and outgoing amounts before receipt cannot be used. This deterministic day-bucket allocation does not invent an intraday order or identify individual banknotes/funds. Duplicate transaction rows remain; source precision is retained without rounding before comparisons.

The account `temporal` JSON object reports `incoming_kzt`, `outgoing_kzt` (both excluding self-transfers), `matched_kzt`, `matched_day1_kzt`, `matched_day2_kzt`, `matched_in_share`, and `matches` with incoming/outgoing ISO dates, lag in calendar days and KZT. Day-1 and day-2 values partition the SAME two-day FIFO allocation; they are not independent reruns with different windows. Each amount is used once per account allocation, while a transfer naturally appears as outgoing at its payer and incoming at its recipient.

`same_day_overlap_kzt` sums min(daily incoming, daily outgoing), with dated rows in `same_day`. It is an independent, non-additive descriptive measure: it may overlap amounts used in strict-future matching, never increases transit support and cannot establish direction within the day. Self-transfers are excluded from both measures.

The denominator is ALL observed non-self incoming amounts, including unmatched and late-month receipts; zero incoming gives a null share. `end_window_incoming_kzt` identifies receipts on July 30–31 whose full two-day follow-up extends beyond the documented July 31 collection end. Do not infer the observation end from the last transaction. Missing later data and boundary truncation can suppress support without disproving transit.

Transit retains the monthly out/in ratio 0.8–1.2 and non-seed/peer requirements and additionally requires matched incoming share >=0.8. The new gate is a transparent heuristic. Base confidence, overlap deductions, boundary/seed multipliers, community algorithm and priority weights are unchanged. The manifest records rule version, method, window and gate. This is evidence of compatible timing, not proof that the same money moved onward.


## Coexisting patterns (patterns version 1)

`patterns` is an ordered list of localized message descriptors with raw numeric parameters. Collection uses I>=3 and I>=2O; distribution uses O>=5 and O>=2I. Fast transit uses the strict-future FIFO share >=0.8, independently of seed status, monthly ratio or the winning role. Its amount and share use non-self transactions. These labels can coexist, are calculated before role selection and never feed back into priority or confidence. They report observed evidence, not confirmed purpose; an empty list means only that none of these thresholds was met. Mandatory CSVs retain one primary role. The card and dashboard JSON carry the additional patterns without adding CSV columns.
