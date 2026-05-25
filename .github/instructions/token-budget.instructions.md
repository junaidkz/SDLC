---
applyTo: '**'
---

# Token-Budget Instructions (all agents inherit)

Token cost is a first-class constraint. Apply these rules unless the user explicitly overrides.

## Read less

1. **Prefer `search` and `usages` over `codebase`.** The `codebase` tool sweeps the whole repo into context. Use it only when you genuinely need a holistic view; otherwise grep for a symbol.
2. **Never re-read what's in `.copilot/context.json`.** The Initiator already discovered the stack, commands, and layout. Read that file once, then act.
3. **Targeted file reads**: open only the files you will edit or that contain the symbol you are tracing. Do not open neighbours "for context".
4. **Truncate large reads.** If a file is > 500 lines, read the relevant range only.

## Write less

1. **No conversational filler.** Skip "Great question!", "Let me think...", "Here's what I'll do" preambles. State the action and do it.
2. **No restating the user's request.** They know what they asked.
3. **Diffs over full files.** When reporting changes, show the diff, not the entire post-change file.
4. **Structured outputs between agents.** Use the agreed JSON / fenced-block schemas. No prose narration of what's already in the structure.

## Loop less

1. **One-shot the plan.** The Planner produces the full plan in one response; it does not "think out loud" across multiple turns.
2. **Batch tool calls.** When multiple independent reads are needed, request them together.
3. **Cache discovery.** If you ran a search and a follow-up question relates to the same results, reference them — do not re-search.
4. **Skip the Planner for trivial changes.** The Orchestrator routes < 20-LOC fixes against an existing REQ-ID directly to the Implementer.

## Right-size the model

Each agent has a `model:` line in its frontmatter chosen for cost-per-quality on its specific task:
- **Initiator / Orchestrator** — small, fast model (routing + discovery only).
- **Requirements Gatherer / Planner** — heavy reasoning model (decomposition errors compound).
- **Implementer** — strong coding model (Sonnet-class).
- **Reviewer** — different family than Implementer for blind-spot diversity.

Do not switch models mid-session without reason.

## Tool scoping (enforced by frontmatter)

Each agent declares only the tools it needs. Read-only agents have no `editFiles` / `runCommands`. This:
- Prevents accidental side effects.
- Shortens the system prompt the model sees (each tool definition costs tokens).
- Makes audit logs easier to interpret.

## Anti-patterns to avoid

- Opening `package.json` / `*.csproj` repeatedly to "check the stack" — it's in `context.json`.
- Re-reading a file after `str_replace` succeeded — the edit was applied.
- Asking the user to confirm something already confirmed in this session.
- Summarising your own previous turn.
