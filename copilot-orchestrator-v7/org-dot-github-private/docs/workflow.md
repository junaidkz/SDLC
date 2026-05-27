# Workflow — Mermaid version

For rendering inline in GitHub/markdown viewers. The SVG (`docs/workflow.svg`) is the polished version; this is the maintainable one.

```mermaid
flowchart TD
    classDef user fill:#3f1d1d,stroke:#FB7185,color:#FECDD3,stroke-width:2px
    classDef router fill:#3f3717,stroke:#FCD34D,color:#FEF3C7,stroke-width:2px
    classDef util fill:#1f2937,stroke:#94A3B8,color:#E5E7EB,stroke-width:1px
    classDef rg fill:#0f3a2d,stroke:#34D399,color:#A7F3D0,stroke-width:2px
    classDef plan fill:#0c2d44,stroke:#38BDF8,color:#BAE6FD,stroke-width:2px
    classDef impl fill:#2b1e4d,stroke:#A78BFA,color:#DDD6FE,stroke-width:2px
    classDef rev fill:#3d1a32,stroke:#F472B6,color:#FBCFE8,stroke-width:2px
    classDef gate fill:#3a2e08,stroke:#FACC15,color:#FEF08A,stroke-width:2px
    classDef audit fill:#0c3340,stroke:#22D3EE,color:#A5F3FC,stroke-width:1px
    classDef jira fill:#142a4a,stroke:#60A5FA,color:#BFDBFE,stroke-width:1px
    classDef done fill:#0f3a2d,stroke:#34D399,color:#D1FAE5,stroke-width:2px

    USER(["👤 USER<br/><i>trigger</i>"]):::user

    ORCH["**Orchestrator**<br/>GPT-5 mini · router<br/><i>no code · enforces gates</i>"]:::router
    INIT["**Initiator**<br/>GPT-5 mini<br/>/scan-repo"]:::util
    CTX[(".copilot/context.json")]:::util

    RG["**Requirements Gatherer**<br/>GPT-5 · interactive<br/>/author-gherkin<br/><i>writes .feature (jira: pending)</i>"]:::rg
    GATE1{{"★ USER GATE 1<br/>approve requirements?"}}:::gate

    PLAN["**Planner**<br/>GPT-5 · READ-ONLY<br/><i>single-shot · plan + AC→test</i>"]:::plan
    GATE2{{"★ USER GATE 2<br/>approve plan?"}}:::gate

    IMPL["**Implementer**<br/>Claude Sonnet 4.5<br/>/stamp-traceability /propose-adr<br/>/append-rtm /emit-audit"]:::impl
    REV["**Reviewer**<br/>o3 · different model family<br/>/review-owasp /emit-audit"]:::rev

    COMMIT[/"commit + PR<br/>[REQ-XXX] · Refs: PLAT-NN<br/>RTM updated"/]:::done
    DONE(["✓ DELIVERED"]):::done

    GHA["**GitHub Action**<br/>create-jira-from-feature.yml<br/><i>on PR open · stdlib python</i>"]:::jira
    JIRA[("Jira<br/>PLAT-1234<br/>source of truth")]:::jira

    JSONL[("audit_log.py<br/>~/.copilot/audit/*.jsonl")]:::audit
    FILEBEAT["Filebeat<br/><i>tails JSONL · ships NDJSON</i>"]:::audit
    ES[("Elasticsearch<br/>copilot-audit-*")]:::audit
    KIBANA["**Kibana**<br/>dashboard · alerts · replay"]:::audit

    USER ==> ORCH
    ORCH -.->|first run| INIT
    INIT -.->|writes| CTX
    INIT -.-> ORCH
    ORCH ==>|behaviour change| RG

    RG ==> GATE1
    GATE1 -.->|revise| RG
    GATE1 ==>|go| PLAN

    PLAN ==> GATE2
    GATE2 -.->|revise| PLAN
    GATE2 ==>|go| IMPL

    IMPL ==>|submit| REV
    REV ==>|REJECTED · findings| IMPL
    REV ==>|APPROVED| COMMIT
    COMMIT -.-> DONE

    COMMIT -.->|on PR open| GHA
    GHA -.->|REST| JIRA
    GHA -.->|writes jira key back| RG

    RG -.->|audit event| JSONL
    PLAN -.->|audit event| JSONL
    IMPL -.->|audit event| JSONL
    REV -.->|audit event| JSONL
    JSONL --> FILEBEAT --> ES --> KIBANA
```

## How to read this

- **Solid arrows** (`==>`): main flow. The user's request flows down, code flows back up after review.
- **Dotted arrows** (`-.->`): asides — first-run discovery, CI automation, audit events, revise loops.
- **Diamonds** (`{{...}}`): human approval gates. Two of them: after requirements, after plan. The user is the only one who can say "go".
- **Cylinders** (`[(..)]`): persistent state — context cache, Jira ticket, JSONL audit log, Elasticsearch.
- **The loop** that matters most: `Implementer ⇄ Reviewer`. It runs as many times as the Reviewer needs to say `APPROVED`. The user does *not* sit in this loop — they set direction at the two gates above it and let the agents iterate.

## Variations

- **Hot fix path**: Orchestrator routes a < 20-LOC defect against an existing REQ-ID directly to the Implementer (skipping RG + Planner). The Reviewer still runs.
- **Stale context**: when `.copilot/context.json` is > 24h old, the Orchestrator re-runs the Initiator before anything else.
- **Audit-only run**: any agent can be invoked individually for inspection; their audit events still ship, so the JSONL pipeline never has gaps.
