# ADR 0006 - Record Architecture Decisions

* Status: accepted
* Deciders: SahiDawa Core Team
* Date: 2026-07-18

Technical Story: [ADR Process Guide](./README.md)

## Context and Problem Statement

SahiDawa is a multi-app monorepo (`apps/web`, `apps/api`, `apps/ml`, `apps/etl`)
with shared packages and several load-bearing technology choices — a monorepo
orchestrator, a primary database, a caching layer, an agent framework, and a
frontend framework. These choices were made deliberately, but the *reasoning*
behind them has historically lived in scattered places: pull request comment
threads, Discord discussions, and contributors' heads.

As the project scales (22 languages, GSSoC contributors, multiple services), that
reasoning becomes a liability:

- **PR comments are not enough.** They are tied to a single change, easy to miss,
  and frequently truncated or resolved-and-forgotten. A reviewer six months later
  cannot reconstruct *why* Redis was chosen over Memcached from a merged diff.
- **Chat history is not enough.** Discord is ephemeral, unindexed by our docs, and
  inaccessible to anyone who wasn't in the room. Decisions made there are
  effectively private and unverifiable.
- **Architectural decisions need durable documentation.** They are expensive to
  reverse and are questioned repeatedly by new contributors. Without a stable
  record, every new person re-litigates the same choices, and the project risks
  accidental drift or contradictory changes.

We need an official, version-controlled mechanism to record significant
architectural decisions and their rationale — one that is easy to find, easy to
search, and stable over time.

## Decision Drivers

* Preserve the "why" behind major technical choices beyond PRs and chat.
* Make decisions discoverable and searchable from the repository's main docs.
* Keep the process lightweight and consistent with open-source best practices.
* Provide a stable, reviewable record that scales as the project grows.
* Avoid reinventing a custom workflow; follow established ADR conventions.

## Considered Options

* **Option 1: Keep decisions in PR comments and Discord only** (status quo).
* **Option 2: Long-form design documents in `docs/architecture/`** without a fixed structure.
* **Option 3: Architecture Decision Records (ADRs)** — short, numbered, MADR-style
  markdown files in `docs/adr/`, each capturing one decision.

## Decision Outcome

Chosen option: **Option 3: Architecture Decision Records (ADRs)**, because it
gives every significant decision a permanent, grep-able home with a consistent
shape, while staying cheap to write and review. It builds on conventions the
community already knows (Michael Nygard ADRs and MADR), so contributors don't have
to learn a bespoke process.

This ADR establishes the system. The process, numbering rules, status definitions,
and an index are maintained in [`docs/adr/README.md`](./README.md); new records
start from [`docs/adr/template.md`](./template.md).

### Consequences

* **Good:**
  * The rationale for major choices (Turborepo, Supabase, Redis, LangGraph, Next.js)
    is now explicit and reviewable, not buried in threads.
  * New contributors can understand *and trust* existing architecture from one folder.
  * Decisions are version-controlled, diffable, and linkable from issues and PRs.
  * Superseding an old decision is a clean, auditable act (new ADR + status change),
    not silent edits.
* **Bad:**
  * Adds a small documentation discipline: contributors must pause to write an ADR
    for significant choices rather than only discussing them.
  * Risk of ADR sprawl if the "when not to create one" guidance is ignored — mitigated
    by the rules in `docs/adr/README.md` and maintainer review.

## Pros and Cons of the Options

### Option 1: Keep decisions in PR comments and Discord only

* **Good:** Zero extra process; decisions happen where work already happens.
* **Bad:** Ephemeral, unsearchable, inaccessible to latecomers, and easy to
  contradict later without anyone noticing.

### Option 2: Long-form design documents without structure

* **Good:** Room for deep explanation.
* **Bad:** No consistent format, no numbering, no status lifecycle; hard to scan and
  easy to let go stale.

## What should trigger a future ADR

A new ADR should be opened when a change is architecturally significant, hard to
reverse, cross-cutting, or likely to be questioned later. Concrete triggers in this
project include, but are not limited to:

- Adopting or replacing a core framework, runtime, or orchestration tool.
- Choosing or changing the primary database, cache, message queue, or search engine.
- Introducing a new cross-cutting pattern (auth, observability, offline sync, agent
  orchestration).
- Changing the monorepo structure, build pipeline, or deployment topology.
- Reversing or materially changing any previously accepted ADR.

Routine bug fixes, localized refactors, styling, and per-PR contribution tracking
are explicitly out of scope — the latter is handled by `docs/devtrack/adr/`.
