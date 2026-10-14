#!/usr/bin/env bash
# Rebuild ai-log.txt (gitignored) from the Claude Code session transcripts of this project.
# Usage (Git Bash or any POSIX shell, from anywhere in the repo):  sh scripts/update-ai-log.sh
set -eu

ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"

for py in python3 python py; do
  if command -v "$py" >/dev/null 2>&1 && "$py" -c "import sys; sys.exit(sys.version_info < (3, 9))" 2>/dev/null; then
    PYTHONIOENCODING=utf-8 exec "$py" "$ROOT/scripts/ai_log.py" "$ROOT/ai-log.txt"
  fi
done

echo "Cần Python 3.9+ (python3, python hoặc py) để chạy scripts/ai_log.py" >&2
exit 1
