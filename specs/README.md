# Nyx Specs

This directory is the source of truth for Nyx's design and implementation intent. Code follows these docs, not the reverse — when a decision changes, update the spec in the same commit.

## Documents

| Document | Purpose |
|----------|---------|
| [`system-architecture.md`](system-architecture.md) | Authoritative design spec: components, interfaces, data models, event schemas, M1 limitations |
| [`MILESTONE_1.md`](MILESTONE_1.md) | Dependency-ordered implementation checklist for M1 (MVP). Start here when writing code. |
| [`user-stories/`](user-stories/) | Workflow stories in Gherkin format. Used to validate and stress-test the architecture spec. |
| [`research/`](research/) | Background research and curated reference links that informed design decisions. |

## Reading Order

1. **New to Nyx?** Start with `system-architecture.md` Section 1 (System Purpose) and Section 2 (Design Principles).
2. **Implementing M1?** Work through `MILESTONE_1.md` step by step. Cross-reference `system-architecture.md` for interface contracts.
3. **Reviewing a design decision?** Read the relevant section of `system-architecture.md`, then read the corresponding user story to see what the decision needs to support.
4. **Found a spec gap?** Grep for `SPEC GAP` in `user-stories/` — unresolved questions are marked inline. Resolve them by updating `system-architecture.md` and removing the gap marker.

## Conventions

- **SPEC GAP** markers in user stories signal missing or ambiguous decisions in `system-architecture.md`. They are intentional — the stories exist to surface gaps, not to hide them.
- Do not write implementation notes here. Decisions belong in `system-architecture.md`; code belongs in `src/`.
- Research that informed a decision should stay in `research/` even after the decision is made, so the reasoning is traceable.
