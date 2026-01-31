#!/bin/bash
# Squash history into two clean commits: init + one full project commit.
# Run from repo root. After running, push with: git push --force-with-lease origin main

set -e

cd "$(git rev-parse --show-toplevel)"

echo "Current branch: $(git branch --show-current)"
echo "This will reset to commit 41239ca (init) and create one new commit with the current tree."
echo "You will need to force-push: git push --force-with-lease origin main"
read -p "Continue? (y/N) " -n 1 -r
echo
[[ $REPLY =~ ^[Yy]$ ]] || exit 0

# Stash any uncommitted changes so we don't lose them
git stash push -u -m "cleanup-git-history-stash" 2>/dev/null || true

# Soft reset to first commit (init); keeps current tree, unstaged
git reset --soft 41239ca

# Stage everything (current state of repo)
git add -A

# One clean commit describing the project
git commit -m "PiFM: Raspberry Pi FM radio receiver

- Backend: Flask API, rtl_fm/sox/ffmpeg pipeline, lsusb-only status
- Frontend: web UI (player, presets, gain control, status)
- Installer: one-command install, udev, user groups, systemd
- Docs: INSTALL, TROUBLESHOOTING, DEVELOPMENT
- Default gain 0 and 170k sample rate for stable SDR use"

echo ""
echo "Done. History is now:"
git log --oneline

if git stash list | grep -q cleanup-git-history-stash; then
  echo ""
  echo "Restore stashed changes with: git stash pop"
fi
echo ""
echo "Push with: git push --force-with-lease origin main"
