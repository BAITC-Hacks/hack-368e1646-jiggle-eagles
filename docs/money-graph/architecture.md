# Delivered local architecture

```mermaid
flowchart LR
    P[Local nodes / edges / transactions Parquet] --> V[pandas + PyArrow validation]
    V --> G[NetworkX DiGraph including isolates]
    G --> C[Undirected weighted Louvain grouping]
    G --> F[Directed observed flow features]
    C --> F
    F --> R[Explainable role rules and priority]
    R --> E[Official CSVs and deterministic JSON]
    E --> M[Run manifest with hashes and timing]
    R --> S[Python loopback HTTP server]
    S --> U[Local HTML + SVG account dashboard]
```

`money_graph/pipeline.py` validates, calculates and serializes. `money_graph/__main__.py` runs the pipeline and optionally serves; `scripts/money-graph.sh` provides the one-command entry point. `money_graph/server.py` holds in-memory results and read-only routes, binding to 127.0.0.1. `money_graph/static/` displays search, account evidence, communities and paginated directed neighborhoods. JSON gids are strings to preserve int64 precision.

The three CSV schemas remain exactly as specified. Dashboard JSON is a deterministic supplementary artifact; timing lives in a separate manifest. Inputs and outputs remain in ignored private local storage. No application LLM, model training, database, authentication, cloud services or external UI assets are required.

The existing Node/React connectivity starter remains separately runnable and is not in this path. There is no Python Docker image or production deployment in this iteration.
