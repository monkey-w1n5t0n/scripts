#!/usr/bin/env bash
# Tests for check-repo-sync script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$SCRIPT_DIR/check-repo-sync"
TEST_DIR="/tmp/check-repo-sync-test-$$"

echo "Testing check-repo-sync..."

# Test 1: Script exists and is executable
if [[ ! -x "$SCRIPT" ]]; then
	echo "❌ FAIL: Script does not exist or is not executable"
	exit 1
fi
echo "✓ PASS: Script exists and is executable"

# Test 2: Script runs without errors on actual ~/src
if ! "$SCRIPT" >/dev/null 2>&1; then
	echo "❌ FAIL: Script returned non-zero exit code"
	exit 1
fi
echo "✓ PASS: Script runs successfully on ~/src"

# Test 3: Script produces output (or at least doesn't crash)
output=$("$SCRIPT" 2>&1)
exit_code=$?
if [[ $exit_code -ne 0 ]]; then
	echo "❌ FAIL: Script crashed with exit code $exit_code"
	echo "Output: $output"
	exit 1
fi
echo "✓ PASS: Script completes without errors"

# Test 4: Output format is correct (repo names only, one per line)
if [[ -n "$output" ]]; then
	# Each line should be a simple repo name (no slashes)
	while IFS= read -r line; do
		if [[ "$line" =~ / ]]; then
			echo "❌ FAIL: Output line contains unexpected format: $line"
			exit 1
		fi
	done <<< "$output"
	echo "✓ PASS: Output format is correct (repo names only)"
else
	echo "⚠ INFO: No repos need syncing (output is empty)"
fi

# Test 5: Script doesn't output duplicate entries
if [[ -n "$output" ]]; then
	unique_count=$(echo "$output" | sort -u | wc -l)
	total_count=$(echo "$output" | wc -l)

	if [[ "$unique_count" -ne "$total_count" ]]; then
		echo "❌ FAIL: Output contains duplicate entries"
		exit 1
	fi
	echo "✓ PASS: No duplicate entries in output"
fi

echo ""
echo "All tests for check-repo-sync passed!"

# Cleanup
rm -rf "$TEST_DIR"
