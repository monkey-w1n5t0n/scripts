# scripts
Scripts. Mostly.

## Tools

### `agent-chat-audit`

Indexes transcript files from `~/.claude`, `~/.claude-gp`, `~/.codex`, and `~/.factory` into a local SQLite cache, then serves a browser UI for reviewing recent sessions without reprocessing full chats.

The UI supports:
- bookmarking sessions for manual review later
- copying the correct per-agent resume command
- permanently hiding transcripts so later ingests do not bring them back
- stripping known Codex `AGENTS.md` onboarding boilerplate from the displayed prompt text

Examples:

```bash
./agent-chat-audit ingest
./agent-chat-audit serve --open
./agent-chat-audit refresh --open
./agent-chat-audit ingest --all
```

`ingest` defaults to the last 7 days so it stays fast on very large transcript stores. Use `--all` if you want a full historical index.
