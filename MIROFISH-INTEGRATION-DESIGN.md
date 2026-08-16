# MiroFish Integration Design

**Date:** 2026-03-26
**Branch:** `mirofish-integration`
**Status:** Design approved; **core layers implemented and wired into the live engine** (graph-backed memory via `GRAPH_MEMORY_ENABLED`, hybrid populations, governance gates, goal trees, topic-aware opinion dynamics). See `CLAUDE.md` → Gotchas for the runtime switches.

## Motivation

MiroFish (43k stars, 6k forks) is a multi-agent simulation engine for predicting public reactions. Upload a document, it generates hundreds of agents with unique personalities that simulate social media interactions. It tracks sentiment evolution, topic propagation, and influence dynamics.

EmotionEngine has better simulation mechanics (physical world, emotion contagion, trust networks, CognitiveEngine, coalition detection, determinism verification). MiroFish has better knowledge infrastructure (GraphRAG, NER/RE pipeline, hybrid search, post-sim analysis tools, agent interviews).

**Goal:** Combine both. EmotionEngine gets MiroFish's knowledge layer and analysis tools. The result is a simulation engine with both rich physical/emotional mechanics AND graph-backed intelligence.

## Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Graph database | Oracle 26ai (SQL/PGQ property graphs) | Stays in Oracle stack, no new dependency, aligns with portfolio |
| Graph query language | SQL/PGQ | Future-proof, no extra PGX server, works via SQLAlchemy raw queries |
| Embedding model | nomic-embed-text via Ollama (768d) | Already running, lightweight, proven by MiroFish |
| Hybrid search weights | 0.7 vector + 0.3 BM25 | MiroFish's proven ratio, Oracle Text + AI Vector Search |
| Memory scope | Run-scoped first, then promotable (Hybrid) | Preserves determinism, enables cross-run learning later |
| Document input | Plain text / markdown | Covers 80% of use cases, simplest pipeline |
| Preset scenarios | Existing disaster scenarios ship as pre-built graph snapshots | Skip NER/RE, same graph tables, identical post-sim analysis |

## Implementation Tiers

### Tier A: Knowledge Layer (implement first)

#### A1. Document Ingestion Pipeline

```
Input (text/markdown OR preset scenario)
    |
TextProcessor -- chunking, cleaning, section detection
    |
NERExtractor -- LLM-based entity/relationship extraction via Qwen3.5
    |
OntologyBuilder -- defines entity types + relation types for this scenario
    |
GraphBuilder -- creates Oracle graph tables, embeds entities, stores relationships
    |
PersonaGenerator -- entities -> agent personas (Big Five + MBTI + opinion bias + influence)
    |
ScenarioAssembler -- wires agents, locations, hazards, initial world state
    |
Ready to simulate
```

**Preset scenarios** (Rising Flood, etc.) ship as pre-built graph snapshots. They skip NER/RE -- entities, relationships, and personas are already defined. They live in the same Oracle graph tables as custom scenarios, so post-sim analysis works identically.

**Custom document flow:** Paste markdown/text -> `NERExtractor` calls LLM router (Qwen3.5) with ontology-guided prompt (MiroFish's approach) -> extracts people, organizations, locations, events, hazards -> `PersonaGenerator` enriches each entity into a full agent persona via second LLM call (generates Big Five traits, MBTI, backstory, opinion biases, influence level from entity context).

**Key difference from MiroFish:** Personas get Big Five traits that mechanically drive the CognitiveEngine (not just prompt flavor text). Traits actually change agent behavior via PersonalityMechanics.

#### A2. Oracle Graph Memory Architecture

**Three graph table sets in Oracle 26ai via SQL/PGQ:**

**1. Scenario Knowledge Graph (static, built at ingestion)**
- Entity nodes: people, organizations, locations, objects, events, hazards
  - Columns: `entity_id`, `graph_id`, `name`, `type`, `summary`, `attributes` (JSON), `embedding` (VECTOR(768)), `created_at`
- Relationship edges: trusts, knows, located_at, caused_by, member_of, owns
  - Columns: `edge_id`, `source_id`, `target_id`, `type`, `fact` (text), `weight`, `embedding` (VECTOR(768)), `created_at`
- Ontology metadata: JSON on a `Graph` row, defines valid entity/relation types per scenario

**2. Agent Memory Graph (dynamic, run-scoped, grows during simulation)**
- Memory nodes: episodic memories, observations, decisions, conversations
  - Columns: `memory_id`, `run_id`, `agent_id`, `type`, `content`, `importance` (1-10), `emotional_valence` (-1.0 to 1.0), `embedding` (VECTOR(768)), `step_number`, `created_at`
- Memory edges: led_to, contradicts, supports, about_entity, about_agent, occurred_at_location
  - Links memories to each other AND to scenario knowledge graph entities
- Replaces flat `AgentMemory` (sliding window of 50 messages + summarization)

**3. Oracle Text + Vector indexes (hybrid search)**
- `VECTOR INDEX` on all embedding columns (cosine similarity)
- `CTXSYS.CONTEXT` full-text index on `content`, `summary`, `fact` columns
- `hybrid_search(query, graph_id, run_id)` -> 0.7 * vector_score + 0.3 * bm25_score -> top-K results

**New agent tick flow:**
```
Agent.tick() ->
  hybrid_search(current_situation, run_id) -> retrieve relevant memories
  graph_traverse(nearby_entities) -> get relationships to people/places in scene
  merge into context window ->
  CognitiveEngine THINK/PLAN/ACT/REFLECT ->
  write new memory node + edges back to graph
```

Agents recall based on *relevance*, not recency. An agent at a hospital might recall a memory from 30 steps ago about medical supplies, even though 50 other messages happened since.

#### A3. Abstract GraphStorage Interface

Same pattern as MiroFish -- a `GraphStorage` ABC:

```python
class GraphStorage(ABC):
    @abstractmethod
    def create_graph(self, name: str, ontology: dict) -> str: ...
    @abstractmethod
    def add_entity(self, graph_id: str, entity: Entity) -> str: ...
    @abstractmethod
    def add_edge(self, graph_id: str, edge: Edge) -> str: ...
    @abstractmethod
    def add_text(self, graph_id: str, text: str) -> str: ...  # NER + embed + store
    @abstractmethod
    def search(self, graph_id: str, query: str, limit: int = 10) -> List[SearchResult]: ...
    @abstractmethod
    def get_neighbors(self, entity_id: str, depth: int = 1) -> SubGraph: ...
    @abstractmethod
    def get_entity(self, entity_id: str) -> Entity: ...
```

Oracle implementation first. Neo4j can be added later behind the same interface.

#### A4. Future: Hybrid Memory Scope (Phase 2)

Run-scoped by default. Later add:
- "Promote" API: mark specific memories as scenario-level persistent
- Scenario-level graph partition: persists across runs
- Cross-run retrieval: agents in run N can retrieve promoted memories from runs 1..N-1
- Preserves determinism (promoted memories are inputs, not side effects)

---

### Tier B: Analysis Layer (implement second)

#### B1. Post-Simulation Deep Interaction

After a run ends, expose a chat endpoint per agent:
- `POST /api/runs/{run_id}/agents/{agent_id}/chat`
- Agent's full memory graph + persona loaded as context
- LLM responds in-character, can explain decisions
- "Why did you refuse to help Marcus?" -> Agent explains via personality + memory + trust history

#### B2. Report Agent with Graph Tools

An automated post-sim analyst. Three retrieval tools (from MiroFish):

1. **InsightForge** (deep search): Takes a question, auto-generates 3-5 sub-questions, runs hybrid search for each, synthesizes findings. Most powerful.
2. **PanoramaSearch** (breadth search): Returns comprehensive view of all entities, relationships, and events. Good for "what happened overall?"
3. **Agent Interviews**: Programmatically interviews a focus group of agents. Selects diverse agents (varied personalities, coalitions, trust levels), asks targeted questions, extracts key quotes.

Report output: structured markdown with sections for timeline, key events, agent behavior analysis, coalition dynamics, trust evolution, recommendations.

#### B3. Interactive Agent Chat

Extend beyond post-sim to mid-simulation:
- Pause simulation, chat with any agent, resume
- "God's-eye view" injection: introduce new information or events mid-sim
- Observer mode: watch agent reasoning in real-time via the existing TUI MindView component

---

### Tier C: Social Dynamics Layer (implement third)

#### C1. Opinion/Sentiment Dynamics

New agent attributes:
- `opinion_vectors`: dict of topic -> stance (-1.0 to 1.0)
- `opinion_bias`: how resistant to opinion change (0.0 = easily swayed, 1.0 = immovable)
- `reaction_speed`: how quickly opinions shift per interaction (ticks)
- `influence_level`: how much this agent's opinions affect others (0.0 to 1.0)

When agents argue, opinions shift based on:
- Influence differential (high influence persuades low influence)
- Trust level (trusted agents are more persuasive)
- Opinion bias (resistant agents shift less)
- Argument quality (LLM-assessed)

#### C2. Sentiment Evolution Tracking

Per-step tracking:
- Topic sentiment distribution across all agents
- Influence cascade graph (who influenced whom, on what topic)
- Opinion convergence/divergence metrics
- Tipping point detection (when consensus forms or collapses)

#### C3. Scaling to 100+ Agents

Lightweight agent mode:
- Not every agent needs full CognitiveEngine every tick
- Background agents: rule-based reactions (personality-driven probabilities, no LLM call)
- Foreground agents: full THINK/PLAN/ACT/REFLECT cycle
- Dynamic promotion: background agents get promoted to foreground when they're in an active scene or addressed directly
- Batch persona generation: generate 100 personas from document entities in one LLM call (batched prompt)

#### C4. Influence Network Visualization

New TUI component + frontend panel:
- Directed graph of influence relationships
- Edge weight = influence strength on specific topics
- Animate opinion propagation over time
- Identify "super-spreaders" and "opinion anchors"

---

## New Files (estimated)

```
backend/app/storage/
    graph_storage.py          # Abstract GraphStorage ABC
    oracle_graph_storage.py   # Oracle 26ai SQL/PGQ implementation
    embedding_service.py      # Ollama nomic-embed-text wrapper
    ner_extractor.py          # LLM-based NER/RE via Qwen3.5
    search_service.py         # Hybrid search (vector + BM25)

backend/app/services/
    document_ingestor.py      # TextProcessor + chunking + ingestion pipeline
    ontology_builder.py       # Defines entity/relation types per scenario
    persona_generator.py      # Entity -> full agent persona (Big Five + MBTI)
    scenario_assembler.py     # Wires graph entities into simulation-ready scenario
    report_agent.py           # Post-sim analysis with graph tools
    graph_tools.py            # InsightForge, PanoramaSearch, QuickSearch

backend/app/agents/
    graph_memory.py           # GraphMemory replacing flat AgentMemory
    agent_interviewer.py      # Programmatic focus group interviews

backend/app/api/
    document.py               # POST /api/documents (upload + ingest)
    chat.py                   # POST /api/runs/{id}/agents/{id}/chat
    report.py                 # POST /api/runs/{id}/report

backend/app/models/
    graph.py                  # SQLAlchemy models for graph tables
    opinion.py                # Opinion vector models (Tier C)
```

## Dependencies

- Oracle 26ai Free (already in stack) -- SQL/PGQ, AI Vector Search, Oracle Text
- Ollama nomic-embed-text (already available) -- embeddings
- No new infrastructure required

## What This Doesn't Change

- SimulationEngine tick loop (same phases, same scene processing)
- CognitiveEngine THINK/PLAN/ACT/REFLECT (enhanced inputs, same pipeline)
- TrustNetwork, NegotiationManager, CoalitionDetector (unchanged)
- vLLM/Ollama LLM router (unchanged, NER/RE uses same router)
- Go TUI (new components added, existing screens untouched)
- Determinism verifier (still works, run-scoped memory is deterministic)
- Existing preset scenarios (converted to graph snapshots, same behavior)

## MiroFish Comparison

| Feature | MiroFish | EmotionEngine + This Design |
|---------|----------|----------------------------|
| Graph DB | Neo4j CE | Oracle 26ai SQL/PGQ |
| Agent count | Hundreds | Hundreds (Tier C lightweight mode) |
| Personality model | MBTI + demographics | Big Five (mechanical) + MBTI + demographics |
| Simulation type | Social media (posts/replies) | Physical world (locations, movement, hazards, inventory) |
| Emotion model | None | Contagion (neuroticism/extraversion weighted) |
| Trust/negotiation | None | TrustNetwork + NegotiationManager |
| Coalition detection | None | Graph-based community detection |
| Memory | Neo4j graph + hybrid search | Oracle graph + hybrid search |
| Post-sim analysis | ReportAgent + InsightForge | ReportAgent + InsightForge + Agent Interviews |
| Post-sim chat | Yes (any agent) | Yes (any agent) |
| Determinism | No | SHA-256 rolling hash verification |
| Opinion dynamics | Implicit (social media behavior) | Explicit vectors + influence network (Tier C) |
| Visualization | Vue frontend | Go TUI + SvelteKit + token streaming |
