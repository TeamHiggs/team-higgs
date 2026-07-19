# AI / agent stack

Authoritative for **product** AI/agent features (decided 2026-07-19). This is
distinct from the platform's *own* engineering team, which runs on Claude Code
agents, not this stack. (The first product, `plant-log`, makes **no** model
calls, so none of this applies to it — it is recorded for products that will.)

## Decisions

- **Orchestration: LangGraph (strict).** Agentic/multi-step product features are
  built as explicit LangGraph state machines. This is the required control layer
  for product agent flows.
- **Model calls: the provider SDK directly.** Talk to models through the
  **Anthropic SDK** (default to the latest, most capable Claude models) rather
  than through a heavy framework abstraction. It is a thin, stable seam on the
  hot path.
- **LangChain: à la carte, by justification.** Individual LangChain components
  (a mature loader/retriever/splitter) may be used where one concretely earns
  its weight, recorded per-use as a decision — **never adopted wholesale.** The
  failure mode we avoid: LangChain-the-kitchen-sink becoming load-bearing and
  breaking on a minor version.

## Cost boundary

Per `docs/stack-devops.md`, model compute stays local/on-subscription; a
product making runtime model calls introduces API billing and is a deliberate,
recorded decision, not a default.
