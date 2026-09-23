# Money Graph data contract and inspected profile

The organizer [dataset README](https://drive.google.com/file/d/1ro-SiY042jv7De0h7tXBDyY8ZKdHz_US/view?usp=sharing), [specification](https://docs.google.com/document/d/1JPLU-G6R25Ge2hVaY2J9cqvrx7FGExj87XKwJPaMz3o/edit?usp=sharing), [dataset archive](https://drive.google.com/file/d/1yHdWaSb6gwPAUrqco-KrwR2U_YhzFQFT/view?usp=sharing) and [Python starter](https://drive.google.com/file/d/1EnMGG22jSH7Mvgt396kKRi3bjAobsomN/view?usp=sharing) were retrieved September 23, 2026. Original bytes are retained under ignored `data/private/money-graph/source/`; selected Parquet members are under `input/`. Only the three documented Parquet members were extracted, excluding archive metadata.

The dataset covers **July 1–31, 2026**, intra-bank outgoing transfers traced from **81 seed clients**, to **four hops**, with a **5,000 KZT minimum individual transfer**. Identifiers are anonymized int64 client IDs; no labeled roles or customer attributes are supplied. Hackathon-only use applies; no redistribution is inferred.

| File | Observed columns and types | Meaning |
| --- | --- | --- |
| `nodes.parquet` | `gid: int64`, `depth: int64`, `is_seed: bool` | Exact client ID, minimum discovery hop 0–4, initial-set membership |
| `edges.parquet` | `src: int64`, `dst: int64`, `sum_kzt: float64`, `n_tx: int64`, `depth: int8` | Payer → recipient; aggregate July KZT; individual transfer count; edge discovery hop 1–4 |
| `transactions.parquet` | `src: int64`, `dst: int64`, `date: date`, `sum_kzt: float64` | Individual transfer with day precision, no time or timezone |

Node minimum depth and edge discovery depth have different meanings. Gids are never converted through floating point; JSON uses decimal strings. Date values are converted to midnight-naive pandas dates for validation only; no sub-day order is inferred. Amounts represent observed transfers, not balances. Edge sums and transaction sums reconcile within `0.01 + 1e-12 × transaction sum` KZT. Fractional values are present: 35 edge amounts and 37 transaction amounts are non-integer. There is no fabricated currency-unit conversion.

## Inspected facts

| Measure | Observed value |
| --- | --- |
| Nodes / directed pairs / individual transactions | 2,248 / 3,119 / 4,840 |
| Seeds | 81 |
| Minimum depth 0 / 1 / 2 / 3 / 4 | 81 / 472 / 462 / 789 / 444 |
| Observed transfer total | 365,890,012.01 KZT |
| Date coverage | July 1–31, 2026 |
| Isolates / self-links | 19 / 0 |
| Weak components including all nodes | 35 |
| Largest two weak components | 1,877 and 270 accounts |
| Duplicate gids / duplicate ordered edge pairs / required-field nulls | 0 / 0 / 0 |
| Identical transaction rows beyond first occurrence | 97, retained |

The source's 16 weak components exclude 19 isolates: the complete-node graph has 35. There are **371**, not 352, accounts outside the largest component; 352 is the count after excluding the 19 isolates. The extra 0.01 KZT in the observed total reflects source precision rather than rounding to the whole-KZT source summary.

Missing outgoing activity at depth four cannot establish terminal status. Incoming funds outside the sample, other banks and transfers below the threshold remain unobserved. Identical transaction rows are not silently deduplicated; per-pair counts reconcile with the edges as supplied.

## SHA-256 provenance

| Local file | SHA-256 |
| --- | --- |
| `source/data.zip` | `0ce15a932439d076033cba159ca7ede8bf49f188892bb4cc0809b1af49492d72` |
| `source/starter.zip` | `89ca8991a81c19bb3880fa2012e34e3c95d3ea6293992ca818667371a04e7112` |
| `source/dataset-README.md` | `b75c54a5b2e653c21bc0fb87a7d422ee590daf4d380d224abbb4fa6d393df26e` |
| `source/specification.txt` | `cf190319a50c14fc8c79f4caae89095ec0101c1be18dbcb8ab54d4da18c60fca` |
| `input/nodes.parquet` | `d2a45b0df6e9352832d5fb09839d10b9e23f898156c3bab263b051b31cc0296d` |
| `input/edges.parquet` | `4e71dde5cd3115bcb26e91202665532ee6581cf8233a9fc8059ea59fb7358a38` |
| `input/transactions.parquet` | `c30c5317b5439591dde86f2058dc47a3d19b2900c055ded994fe547f6fb7e7da` |

Every pipeline run records fresh hashes, algorithm settings, versions, platform and timing in `run_manifest.json`. Independent local acceptance results are retained in `data/private/money-graph/verification.json`. These data-quality checks do not establish role accuracy.
