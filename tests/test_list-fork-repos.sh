#!/usr/bin/env bash
# Tests for list-fork-repos script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$SCRIPT_DIR/list-fork-repos"

echo "Testing list-fork-repos..."

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

# Test 3: Output format is correct (repo names, no slashes)
if [[ -n "$output" ]]; then
	while IFS= read -r line; do
		if [[ "$line" =~ / ]]; then
			echo "❌ FAIL: Output line contains unexpected format (should be repo name only): $line"
			exit 1
		fi
	done <<< "$output"
	echo "✓ PASS: Output format is correct (repo names only)"
else
	echo "⚠ INFO: No fork repos found in ~/src"
fi

# Test 4: Script doesn't output duplicate entries
if [[ -n "$output" ]]; then
	unique_count=$(echo "$output" | sort -u | wc -l)
	total_count=$(echo "$output" | wc -l)

	if [[ "$unique_count" -ne "$total_count" ]]; then
		echo "❌ FAIL: Output contains duplicate entries"
		exit 1
	fi
	echo "✓ PASS: No duplicate entries in output"
fi

# Test 5: All output are valid directories in ~/src
if [[ -n "$output" ]]; then
	while IFS= read -r repo_name; do
		if [[ ! -d "$HOME/src/$repo_name" ]]; then
			echo "❌ FAIL: Listed repo is not a valid directory: $repo_name"
			exit 1
		fi
	done <<< "$output"
	echo "✓ PASS: All listed repos are valid directories"
fi

echo ""
echo "All tests for list-fork-repos passed!"
