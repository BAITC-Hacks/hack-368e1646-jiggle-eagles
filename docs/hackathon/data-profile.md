# Money Graph data contract and inspection status

The [dataset README](https://drive.google.com/file/d/1ro-SiY042jv7De0h7tXBDyY8ZKdHz_US/view?usp=sharing) and [technical specification](https://docs.google.com/document/d/1JPLU-G6R25Ge2hVaY2J9cqvrx7FGExj87XKwJPaMz3o/edit?usp=sharing) were read on September 23, 2026. **This is a source-derived contract, not a profile of downloaded Parquet files.** Archive contents, hashes, observed values and quality checks are pending.

## Source manifest

| Resource | Source / intended local location | State |
| --- | --- | --- |
| Dataset | [data (1).zip](https://drive.google.com/file/d/1yHdWaSb6gwPAUrqco-KrwR2U_YhzFQFT/view?usp=sharing); `data/private/money-graph/` | Not downloaded or inspected |
| Organizer starter | [starter (1).zip](https://drive.google.com/file/d/1EnMGG22jSH7Mvgt396kKRi3bjAobsomN/view?usp=sharing) | Not inspected or incorporated |
| `nodes.parquet` | 2,248 nodes, including all 81 seeds | Source-reported |
| `edges.parquet` | 3,119 unique ordered payer→recipient pairs | Source-reported |
| `transactions.parquet` | 4,840 individual transfers | Source-reported |

These data cover **July 1–31, 2026**, intra-bank outgoing transfers traced from seeds through four hops, with a **5,000 KZT minimum transfer**. Reported node depth counts are 81, 472, 462, 789 and 444 for depths 0–4. There are no labeled correct roles or customer attributes. Source restrictions limit use to the hackathon; raw inputs and account-level outputs belong in ignored local storage.

## Columns defined by the dataset README

| File | Fields and declared types | Meaning |
| --- | --- | --- |
| `nodes.parquet` | `gid: int64`, `depth: int`, `is_seed: bool` | Client ID; minimum discovery hop, zero for seeds; membership of the starting set |
| `edges.parquet` | `src: int64`, `dst: int64`, `sum_kzt: float64`, `n_tx: int64`, `depth: int8` | Payer, recipient, total July transfer amount for the ordered pair, transaction count, discovery hop 1–4 |
| `transactions.parquet` | `src: int64`, `dst: int64`, `date: date`, `sum_kzt: float64` | Payer, recipient, transaction date and individual amount |

Gids are identifiers: preserve int64 values exactly, including across JSON/browser boundaries. A date does not provide time of day or timezone. KZT is an observed transfer amount, not an account balance; values are stored as float64, so precision and aggregation tolerance need a documented policy. Node minimum depth and edge discovery depth are different fields and must not be conflated.

## Collection limits and source checks still needed

- Fourth-hop nodes can have zero observed outflow because collection ended. Do not infer retained money solely from this absence.
- Incoming funds from outside the sampled network are missing. Ratios using observed inflow can be undefined or misleading, especially for seeds. Never clamp ratios above one into a fictitious balance interpretation.
- Transactions below the threshold are invisible. The data cannot establish whether sub-threshold splitting occurred.
- Keep all rows of `nodes.parquet`, including seeds without any observed edges. Build the node universe before adding edges.
- The specification reports 19 seeds absent from edges and 12 appearing only as recipients. Verify these facts on the files before treating them as observed results.
- S §6 reports 16 weak components with a largest size of 1,877, while also reporting 352 nodes outside it. Against 2,248 total nodes, that subtraction is 371. This discrepancy may involve isolated nodes, but the interpretation is unconfirmed: compute components over the complete node universe and report the reconciliation rather than copying a total.

## First inspection checklist

1. Record source URL, retrieval time, archive/file SHA-256 hashes and extraction manifest; retain original bytes locally.
2. Check required columns/dtypes, nulls, finite amounts, exact IDs, depth ranges and seed consistency. Verify every edge/transaction endpoint exists in nodes; do not silently drop invalid rows.
3. Report duplicate gids and ordered edge pairs. Do not deduplicate repeated transaction rows without evidence: identical fields may describe separate real transfers.
4. Reconcile per-pair transaction counts and amounts with edges using the documented numeric tolerance. Never add edge totals to transaction totals as if they were separate money.
5. Verify reported row/depth/seed counts, July date coverage and threshold; investigate any differences instead of forcing the expected numbers.
6. Count isolates, weak components, self-loops and cycles; document graph representation and policies without assigning roles yet.
7. Use synthetic hand-checkable motifs for calculations and the actual supplied dataset for coverage/runtime acceptance. No structural data check establishes role accuracy.
