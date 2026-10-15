#!/usr/bin/env bash
# Review-then-keep log of the prompts sent to Claude Code (ai-log.txt is committed, ai-log-temp.txt is gitignored).
#   sh scripts/update-ai-log.sh          new prompts -> ai-log-temp.txt; delete the ones to drop
#   sh scripts/update-ai-log.sh commit   what is left in ai-log-temp.txt -> ai-log.txt, temp emptied
set -eu

ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
CMD="${1:-collect}"

for py in python3 python py; do
  if command -v "$py" >/dev/null 2>&1 && "$py" -c "import sys; sys.exit(sys.version_info < (3, 9))" 2>/dev/null; then
    PYTHONIOENCODING=utf-8 exec "$py" "$ROOT/scripts/ai_log.py" "$CMD"
  fi
done

echo "Cần Python 3.9+ (python3, python hoặc py) để chạy scripts/ai_log.py" >&2
exit 1
