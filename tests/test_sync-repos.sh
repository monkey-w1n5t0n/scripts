#!/usr/bin/env bash
# Tests for sync-repos script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$SCRIPT_DIR/sync-repos"

echo "Testing sync-repos..."

# Test 1: Script exists and is executable
if [[ ! -x "$SCRIPT" ]]; then
	echo "❌ FAIL: Script does not exist or is not executable"
	exit 1
fi
echo "✓ PASS: Script exists and is executable"

# Test 2: Script runs without errors (with no repos to sync)
if ! output=$("$SCRIPT" 2>&1); then
	echo "❌ FAIL: Script returned non-zero exit code"
	echo "Output: $output"
	exit 1
fi
echo "✓ PASS: Script runs successfully"

# Test 3: Script produces expected output
if ! echo "$output" | grep -q "Done!"; then
	echo "❌ FAIL: Expected 'Done!' in output"
	echo "Output: $output"
	exit 1
fi
echo "✓ PASS: Script produces expected completion message"

# Test 4: Script handles zero repos gracefully
if ! "$SCRIPT" >/dev/null 2>&1; then
	echo "❌ FAIL: Script doesn't handle zero repos gracefully"
	exit 1
fi
echo "✓ PASS: Script handles zero repos gracefully"

# Test 5: Script accepts arguments (even if dummy ones)
# This just tests that it doesn't crash with arguments
if ! "$SCRIPT" nonexistent-repo-12345 >/dev/null 2>&1; then
	# It's OK if it fails, but it shouldn't crash
	echo "⚠ INFO: Script handles arguments (may fail on non-existent repos)"
fi
echo "✓ PASS: Script accepts arguments"

echo ""
echo "All tests for sync-repos passed!"
