# Investigation contract

The optional investigation agent operates inside Analyses → Analysis details. Python discovers candidates over the full supplied graph; the agent chooses follow-up checks through read-only tools and proposes supported investigations or records insufficient evidence. It cannot change calculations or infer customer attributes.

## Identity and evidence

A calculation snapshot has a schema version, actual method configuration, frozen method descriptions, all node/edge results, daily payer→recipient aggregates, limitations and input hashes. Its hash is the evidence namespace. Analysis IDs identify saved runs; snapshot hashes identify their immutable contents. Changing a threshold or community method creates new results. Existing reviews and briefs keep their original evidence. Legacy results remain available with explicitly missing temporal capabilities.

IDs are exact decimal int64 strings. Amounts use KZT and count observed transfers; daily amounts retain reconciled float64 source precision. Dates are ISO days without timezone. Collection follows outgoing transfers through four hops, July 2026, intra-bank, at least 5,000 KZT; incoming activity outside the sample is missing. Repeated rows are retained; no transaction ID permits deduplication. No temporal result establishes intraday sequencing, complete balances or that the same funds moved onward.

## Discovery and investigation

Shared recipients use a configured minimum distinct incoming-peer count. Community connections use observed directed cross-community pairs. Repeated connections use configured minimum distinct active dates on a directed pair. Discovery enumerates candidates independently of the priority queue and 50-account display limit. Candidates are deterministically interleaved across pattern/component buckets, and overlapping suggestions are deduplicated by candidate. Found, selected and examined counts remain distinct; a limited review is partial.

Tools expose context, candidates, accounts, communities, directed connections, daily activity and evidence, with bounded pages, total/returned/omitted counts and limitations. Every execution is tied to one snapshot. Checks record actual tool arguments and results, not private model reasoning. Findings cite structured measurements retrieved during that review. References, entities, values, units and required follow-up checks are validated before publication. Interpretations remain hypotheses and undergo separate live evaluation.

## Review lifecycle

Reviews persist independently of calculation exports and include snapshot, discovery/tool/prompt versions, model, locale, limits, usage and configured price basis. A completed compatible review can be reused. Partial, failed or interrupted reviews remain inspectable and do not masquerade as complete. Cancellation is terminal and ignores late findings; an already transmitted provider request may finish and incur usage, which is retained when received. On restart, unfinished reviews become interrupted. A brief freezes the validated suggestion, supporting evidence, checks and provenance without another model call.

## Acceptance

MG-AG-01: immutable methods/evidence, original exports preserved on reopen. MG-AG-02: whole-graph discovery with measured reasons and diverse coverage. MG-AG-03: versioned validated tools, independent of display limits. MG-AG-04: adaptive bounded Responses loop and supported findings. MG-AG-05: suggestions, focus/restore, Findings/Checks/Evidence, follow-up and saved brief dialog. MG-AG-06: persistence, compatibility, budgets, cancellation, failure and analysis isolation. MG-AG-07: synthetic calculation/contract/browser checks and separately invoked live evaluation against a deterministic baseline, including counterexamples and cost/latency reporting.
