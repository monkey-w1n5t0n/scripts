#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$SCRIPT_DIR/agent-chat-audit"

echo "Testing agent-chat-audit..."

if [[ ! -f "$SCRIPT" ]]; then
	echo "FAIL: script file is missing"
	exit 1
fi

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

mkdir -p \
	"$tmpdir/claude/projects/workspace" \
	"$tmpdir/codex/sessions/2026/03/11" \
	"$tmpdir/factory/sessions/demo"

cat >"$tmpdir/claude/projects/workspace/session.jsonl" <<'JSON'
{"parentUuid":null,"isSidechain":false,"userType":"external","cwd":"/tmp/project-a","sessionId":"claude-session","type":"user","message":{"role":"user","content":"Investigate the broken deploy script and tell me what I still need to do."},"timestamp":"2026-03-10T10:00:00Z"}
{"parentUuid":"1","isSidechain":false,"userType":"external","cwd":"/tmp/project-a","sessionId":"claude-session","type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"I fixed the failing command path. Please confirm whether you want me to commit the change."}]},"timestamp":"2026-03-10T10:05:00Z"}
JSON

cat >"$tmpdir/codex/sessions/2026/03/11/session.jsonl" <<'JSON'
{"timestamp":"2026-03-11T11:59:00Z","type":"session_meta","payload":{"id":"codex-session","timestamp":"2026-03-11T11:58:00Z","cwd":"/tmp/project-b"}}
{"timestamp":"2026-03-11T12:00:00Z","type":"response_item","payload":{"type":"message","role":"user","content":[{"type":"input_text","text":"Please review the last commit and call out anything risky."}]}}
{"timestamp":"2026-03-11T12:02:00Z","type":"response_item","payload":{"type":"message","role":"assistant","content":[{"type":"output_text","text":"I found one regression. Do you want me to patch it now?"}]}}
JSON

cat >"$tmpdir/factory/sessions/demo/session.jsonl" <<'JSON'
{"type":"session_start","id":"factory-session","cwd":"/tmp/project-c"}
{"type":"message","id":"u1","timestamp":"2026-03-09T09:00:00Z","message":{"role":"user","content":[{"type":"text","text":"Implement the dashboard filters and verify the tests."}]}}
{"type":"message","id":"a1","timestamp":"2026-03-09T09:15:00Z","message":{"role":"assistant","content":[{"type":"text","text":"All tests pass and the filters are implemented."}]}}
JSON

db_path="$tmpdir/index.sqlite"
"$SCRIPT" \
	--db-path "$db_path" \
	--root "claude=$tmpdir/claude" \
	--root "claude-gp=$tmpdir/claude-gp" \
	--root "codex=$tmpdir/codex" \
	--root "factory=$tmpdir/factory" \
	ingest >/dev/null

python3 - "$db_path" <<'PY'
import json
import sqlite3
import sys

db_path = sys.argv[1]
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

session_count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
assert session_count == 3, session_count

claude = conn.execute("SELECT * FROM sessions WHERE agent = 'claude'").fetchone()
assert claude["session_id"] == "claude-session"
assert "Investigate the broken deploy script" in claude["first_user_message"]
assert "commit the change" in json.loads(claude["last_agent_messages_json"])[0]
assert claude["attention_score"] > 0.3

codex = conn.execute("SELECT * FROM sessions WHERE agent = 'codex'").fetchone()
assert codex["cwd"] == "/tmp/project-b"
assert "review the last commit" in codex["first_user_message"]

factory = conn.execute("SELECT * FROM sessions WHERE agent = 'factory'").fetchone()
assert factory["attention_score"] < claude["attention_score"]

message_count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
assert message_count == 6, message_count
PY

echo "PASS: agent-chat-audit ingests representative session files"
