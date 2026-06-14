#!/usr/bin/env bash
# Tests for list-all-repos script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$SCRIPT_DIR/list-all-repos"

echo "Testing list-all-repos..."

# Test 1: Script exists and is executable
if [[ ! -x "$SCRIPT" ]]; then
	echo "❌ FAIL: Script does not exist or is not executable"
	exit 1
fi
echo "✓ PASS: Script exists and is executable"

# Test 2: Script runs without errors
if ! output=$("$SCRIPT" 2>&1); then
	echo "❌ FAIL: Script returned non-zero exit code"
	echo "Output: $output"
	exit 1
fi
echo "✓ PASS: Script runs successfully"

# Test 3: Output contains repo names (owner/repo format)
if [[ -z "$output" ]]; then
	echo "❌ FAIL: Script produced no output"
	exit 1
fi
echo "✓ PASS: Script produced output"

# Test 4: Output format is correct (each line should contain /)
if ! echo "$output" | grep -q "/"; then
	echo "❌ FAIL: Output does not contain expected format (owner/repo)"
	exit 1
fi
echo "✓ PASS: Output format is correct (owner/repo)"

# Test 5: Output is non-empty list
repo_count=$(echo "$output" | wc -l)
if [[ "$repo_count" -lt 1 ]]; then
	echo "❌ FAIL: Expected at least 1 repo, got $repo_count"
	exit 1
fi
echo "✓ PASS: Found $repo_count repos"

echo ""
echo "All tests for list-all-repos passed!"
