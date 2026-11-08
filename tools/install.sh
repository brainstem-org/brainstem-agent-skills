#!/usr/bin/env bash
# Copy the BrainSTEM skills into an agent's skills directory.
#
#   tools/install.sh claude            # ~/.claude/skills        (Claude Code, all projects)
#   tools/install.sh claude --project  # ./.claude/skills        (Claude Code, current project)
#   tools/install.sh codex             # ~/.agents/skills        (Codex, all projects)
#   tools/install.sh codex --project   # ./.agents/skills        (Codex, current repository)
#   tools/install.sh <directory>       # any directory that holds <skill>/SKILL.md folders
#
# Existing brainstem-* skill folders in the target are replaced; nothing else is touched.
set -euo pipefail

repo="$(cd "$(dirname "$0")/.." && pwd)"
target="${1:?usage: tools/install.sh claude|codex|<directory> [--project]}"
scope="${2:-}"

case "$target" in
  claude) base=".claude/skills" ;;
  codex) base=".agents/skills" ;;
  *) base="" ;;
esac

if [ -n "$base" ]; then
  if [ "$scope" = "--project" ]; then dest="$PWD/$base"; else dest="$HOME/$base"; fi
else
  dest="$target"
fi

mkdir -p "$dest"
for skill in "$repo"/skills/*/; do
  name="$(basename "$skill")"
  [ -f "$skill/SKILL.md" ] || continue
  rm -rf "${dest:?}/$name"
  cp -R "$skill" "$dest/$name"
  echo "installed $name -> $dest/$name"
done
