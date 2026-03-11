# scripts
Scripts. Mostly.

## Tools

### `agent-chat-audit`

Indexes transcript files from `~/.claude`, `~/.claude-gp`, `~/.codex`, and `~/.factory` into a local SQLite cache, then serves a browser UI for reviewing recent sessions without reprocessing full chats.

Examples:

```bash
./agent-chat-audit ingest
./agent-chat-audit serve --open
./agent-chat-audit refresh --open
./agent-chat-audit ingest --all
```

`ingest` defaults to the last 7 days so it stays fast on very large transcript stores. Use `--all` if you want a full historical index.
