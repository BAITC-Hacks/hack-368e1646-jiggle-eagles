# Money Graph — HackAlem AI task brief

**Track:** Finance · **Task owner:** Freedom

**Official title:** «Граф денег: восстановление финансовой структуры организованной группы по транзакционной сети»

This brief summarizes the organizer's specification. The task sources and supplied archives were checked on September 23, 2026. It describes the required solution, not implementation status. Repository acceptance criteria and requirement IDs are in [requirements](../hackathon/requirements.md).

## What to build

An investigation tool for a bank's anti-money-laundering analyst: reconstruct a financial network from transaction data, propose participant roles, group related accounts, and explain which accounts deserve investigation first. Deliver a pipeline and a viewing interface; a web page, notebook, or desktop app is acceptable.

## Provided data

The supplied archive contains **2,248 nodes, 3,119 directed connections, and 4,840 transactions**, covering **July 1–31, 2026**. These counts and dates were confirmed from the Parquet files.

- Collection starts from **81 seed clients**, follows only outgoing transfers through **four hops**, and includes only **intra-bank transfers of at least 5,000 KZT**.
- Identifiers are anonymized; the specification describes `gid` as a synthetic identifier without a link to a person's identity. There are no labeled correct roles or customer attributes.
- This is a one-off batch export; live transaction streaming is not required.

| File in `data/` | Rows | Meaning and fields |
| --- | ---: | --- |
| `nodes.parquet` | 2,248 | One client per row, including seeds: `gid`, `depth`, `is_seed` |
| `edges.parquet` | 3,119 | One unique ordered payer → recipient pair, aggregated over July: `src`, `dst`, `sum_kzt`, `n_tx`, `depth` |
| `transactions.parquet` | 4,840 | One individual transfer: `src`, `dst`, `date`, `sum_kzt` |

Client identifiers are `int64`; amounts are `float64` in KZT. Transaction dates have day precision. Node `depth` is the minimum discovery hop (0 for seeds); edge `depth` is the discovery hop (1–4). The dataset README defines the complete input schema.

## Required features

1. **One reproducible local run:** process raw Parquet through all three CSV exports without manual intermediate steps, in **under five minutes on an ordinary laptop**. The jury runs the README command on a clean machine. The timing covers the full recalculation, including export generation.
2. **Complete node coverage:** assign every input node a role, role confidence, cluster, investigation priority, and readable evidence. Include isolated nodes.
3. **Explainable rules:** document a formal rule or metric with a threshold for each role. Explain every priority ranking. When the jury names three arbitrary `gid` values, explain their roles from computed metrics within one minute.
4. **Cluster summaries:** group the network and report each cluster's size, seed count, internal turnover, leading nodes, and a hypothesis about its structure or purpose.
5. **Priorities and visualization:** rank at least 20 nodes with explanations, and show transfer directions, roles, and clusters. Support search by `gid`; during the demo, find a jury-selected node and show its links.

The mandatory minimum role keys are `consolidator`, `transit`, `distributor`, `terminal`, `coordinator`, and `peripheral`. They represent consolidation, pass-through activity, distribution, a possible endpoint, coordination, and peripheral participation. Extensions are allowed if documented. Every assignment remains an investigation hypothesis.

## Required CSV contracts

The specification fixes the required columns below. The organizer starter permits additional columns, but required columns must remain present and populated.

| File | Required columns, in source order | Coverage |
| --- | --- | --- |
| `nodes_roles.csv` | `gid,role,role_score,cluster_id,priority_score,evidence` | Exactly one row for each of the 2,248 supplied nodes, including isolates |
| `clusters.csv` | `cluster_id,n_nodes,n_seed,sum_kzt_internal,top_gids,hypothesis` | One row per cluster; every node has a cluster assignment |
| `top_nodes.csv` | `rank,gid,role,priority_score,why` | At least 20 nodes, ranked by investigation priority, with a text rationale |

For `nodes_roles.csv`, `gid` is `int64`, `role` is a string from the documented dictionary, `cluster_id` is an integer, and `role_score` and `priority_score` are floats in **[0,1]**. `evidence` is a nonempty, human-readable explanation of **at most 200 characters**. The starter README calls for actual numbers in the evidence, rather than an unsupported label such as “high score.”

Role confidence and investigation priority are separate outputs. With no labeled roles, these scores do not establish calibrated probabilities of wrongdoing or supervised classification accuracy.

## Required deliverables

- **Repository:** source code for the pipeline and viewing interface.
- **README:** one-command launch instructions, role criteria and thresholds, output descriptions, limitations, and a discussion of what would change at approximately **one million nodes**. Scaling implementation is not required.
- **Exports:** populated `nodes_roles.csv`, `clusters.csv`, and `top_nodes.csv` using the required contracts.
- **Architecture diagram:** one slide or diagram showing data → metrics → roles → interface.
- **Five-minute live demo:** a live run and substantive walkthrough of **2–3 nodes**, with the search and explanation behavior described above.

## Data limits that affect interpretation

- **Four-hop boundary:** all 444 depth-4 nodes have no observed outgoing transfers. Collection stopped there; zero out-degree alone does not establish that funds remained with the recipient.
- **Missing incoming flows:** funds received from outside the sampled network are absent, especially affecting seeds. Observed inflows and outflows cannot establish a full account balance; an outflow/inflow ratio above one can reflect incomplete coverage.
- **Transfer scope:** external-bank transfers and transfers below 5,000 KZT are absent. Splitting transfers below that threshold is invisible in this dataset.
- **Isolates:** 19 seeds occur in `nodes.parquet` but in no edges; another 12 seeds occur only as recipients. Preserve all supplied nodes when constructing the graph and exports.
- **Component counts:** archive inspection confirms 35 weakly connected components when all nodes are included. The specification's 16 components and 352 nodes outside the largest component exclude the 19 isolates. Including them gives 371 nodes outside the largest component, whose size is 1,877.
- **No identity or role ground truth:** seed membership, structural roles, and clusters do not independently prove wrongdoing. Evaluation focuses on justified criteria and explanations.

## Important constraints

- Frame conclusions as hypotheses for human investigation, never accusations.
- Do not invent customer attributes or enrich the records from external sources. The solution must not assume access to names, personal identification numbers, demographics, income, organizations, or balances.
- Do not hardcode lists of `gid` values as the “correct answer” in place of calculations. Unexplained role predictions do not satisfy the task.
- The supplied data is authorized **solely for use within the hackathon**; anonymization does not grant general redistribution rights.
- Core reproduction must run locally without a cloud cluster, GPU training, or paid services. The specification permits runtime internet access for an optional external LLM API. Any language and libraries are allowed; Python is recommended, not required.

## Optional extensions and organizer starter

An optional AI assistant can answer questions about the graph with references to nodes and generate evidence-based node summaries. A custom ML model is not required. Other optional extensions include temporal patterns, repeated routes and cycles, anomaly detection, node-removal analysis, and recommendations for filling data gaps.

The specification evaluates awareness of collection limits in §6 and separately lists an enhanced method for distinguishing terminal recipients from truncated nodes as optional in §8. Respect the known limitations even without implementing that extension.

The organizer's `starter/` archive includes loading, basic directed-graph metrics, and export templates. It leaves roles, clusters, and priorities unfinished and does not supply the visualization; it is not a complete submission.

## Evaluation

| Criterion | Points |
| --- | ---: |
| Task completion and functionality | 25 |
| Technical implementation | 25 |
| README and reproducibility | 25 |
| Practical value | 15 |
| Originality and development potential | 10 |
| **Total** | **100** |

## Task sources

- [Hackathon tracks page — Finance / Freedom](https://edu.astanahub.com/hackathons/df4743f5-c492-415c-b45a-1f13adb78e06?tab=tracks)
- [Full technical specification — requirements, constraints, deliverables, and scoring](https://docs.google.com/document/d/1JPLU-G6R25Ge2hVaY2J9cqvrx7FGExj87XKwJPaMz3o/edit?usp=sharing)
- [Dataset README — collection parameters and input schemas](https://drive.google.com/file/d/1ro-SiY042jv7De0h7tXBDyY8ZKdHz_US/view?usp=sharing)
- [Dataset archive — data (1).zip](https://drive.google.com/file/d/1yHdWaSb6gwPAUrqco-KrwR2U_YhzFQFT/view?usp=sharing)
- [Organizer starter — starter (1).zip](https://drive.google.com/file/d/1EnMGG22jSH7Mvgt396kKRi3bjAobsomN/view?usp=sharing)

## Shared participant resources

These links are listed on the organizer page. Their contents were outside this task-specific fact-check; consult them for current event-wide rules and submission instructions.

- [Hackathon rules](https://drive.google.com/open?id=1GkZG7O9ME2N7BlTZUQ3Ih1l2kstCxbdN)
- [Participant instructions](https://drive.google.com/file/d/105Rnhzg3Q5tKjfGZIddRqY13kmq_w4r_/view?usp=sharing)
- [OpenAI and NVIDIA information](https://drive.google.com/file/d/1UU1UFeiWkfKEhGHjOApHy6zSxi6_HQfb/view?usp=sharing)
- [Equipment information](https://drive.google.com/file/d/1_at59RgO_L01LGZ_5oE2O9HIu3H50-b6/view?usp=drive_link)
- [Safety information](https://drive.google.com/file/d/1iq6W0b4wYYlhWEcqqbJ3TrRVuKuQ9d5S/view?usp=drive_link)
- [ASU course](https://drive.google.com/file/d/1tIyhzMgHAsQMLa2g66k1f4HXAWnc0I_1/view?usp=sharing)
