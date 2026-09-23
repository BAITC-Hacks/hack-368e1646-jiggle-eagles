# Role hypotheses and evidence design

This is a **design guide**. No classifier, thresholds or ranking formula is implemented yet. Before MG-03 can pass, document the actual equations, thresholds, overlaps, fallbacks, cluster algorithm and score normalization used by the code.

## Role vocabulary

These descriptions follow the task specification. Signals are candidate evidence, not chosen classification rules.

| Export role | Investigation hypothesis | Candidate evidence and caution |
| --- | --- | --- |
| `consolidator` | Multiple participants transfer funds toward a collecting point | Distinct incoming neighbors and observed incoming amount; missing onward edges do not prove retention |
| `transit` | Observed funds pass through a node | Incoming/outgoing amounts, counterparties and available dates; source flow coverage and zero denominators matter |
| `distributor` | A node sends funds to many recipients | Distinct outgoing neighbors, transfer counts and amounts; fan-out alone is not evidence of illicit activity |
| `terminal` | A candidate endpoint of observed flows | Inflow and limited observed onward activity; fourth-hop truncation prevents treating zero out-degree as proof |
| `coordinator` | A node may connect or organize parts of the observed network | Documented bridge/centrality or cross-cluster structure; never infer a person's intent or identity |
| `peripheral` | Available evidence does not support a stronger structural role | Sparse observed activity, isolation or ambiguity; lack of evidence does not establish innocence or guilt |

## Features and units

Build the full node universe from `nodes.parquet`, then attach directed payer→recipient edges. Distinct counterparty counts are graph degrees; `n_tx` counts transactions, not neighbors. Compute observed incoming/outgoing KZT sums from a single consistent representation. Transaction rows can provide date-level patterns; do not invent sub-day timing or double-count edge aggregates alongside raw transfers.

Distinguish node minimum depth from edge discovery depth. Preserve isolates and disconnected components. If a clustering algorithm uses an undirected projection, document the projection and keep original direction for flow analysis and display. Internal cluster turnover counts an observed directed transfer once when both endpoints share the cluster; it is not unique wealth or a balance.

## Confidence and priority

Role score describes support for the selected hypothesis under the documented rules. Priority score describes the order in which an analyst should investigate. Keep both in [0,1] and expose their ingredients separately. Without labeled roles, do not present either as calibrated probability or measured accuracy.

Record missingness, boundary status, contradictory signals and ambiguous roles in evidence. Define tie handling and stable sorting by exact gid so repeated runs do not reorder equally ranked nodes. Seed membership and high amounts alone must not become assertions of criminality. No hardcoded lists of gids may substitute for calculations.

Each node needs concise evidence, at most 200 characters in `nodes_roles.csv`, linking its role to actual measured features and relevant caveats. The top list may provide fuller reasoning in `why`. Display detail beyond the compact CSV field where needed; shorten safely without erasing caveats.

## Collection-aware interpretation

- Depth 4 is a collection boundary: missing onward activity may be unobserved, not absent. Expose this caveat in the graph and explanation.
- The network omits incoming funds from outside the sample. Outflow/inflow ratios can exceed one, especially for seeds; undefined ratios must remain explicit. Do not describe observed net flow as retained funds or account balance.
- Only intra-bank transfers ≥5,000 KZT are included. No inference about invisible smaller transfers, other banks, customer attributes or identity is supported.
- A cluster is an algorithmic grouping of observed links, not proof of a criminal organization. Explain its topology and uncertainty.

Use hand-checkable motifs and boundary counterexamples for automated verification. Report sensitivity to reasonable threshold or clustering changes as an optional robustness check, not a source of ground-truth labels.
