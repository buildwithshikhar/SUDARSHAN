#!/usr/bin/env bash
# Fails if a tracked file contains wording that must not appear in the repository.
# The pattern is assembled from fragments so this file never contains the words itself.
set -euo pipefail
cd "$(dirname "$0")/.."

a="cla""ude"; b="anthr""opic"; c="co-auth""ored-by"; d="generated"" with"
e="so""lo"; f="single"" developer"; g="one"" developer"; h="AI""-assisted"
i="son""net"; j="op""us"; k="hai""ku"

loose="$a|$b|$c|$d|$f|$g|$h"
words="$e|$i|$j|$k"

hits=$(git ls-files -z | xargs -0 grep -InEi "$loose" 2>/dev/null || true)
hits+=$(git ls-files -z | xargs -0 grep -InEiw "$words" 2>/dev/null || true)

if [ -n "${hits// /}" ]; then
  echo "check_wording: forbidden wording in tracked files:" >&2
  echo "$hits" | cut -c1-200 >&2
  exit 1
fi
echo "check_wording: ok"
