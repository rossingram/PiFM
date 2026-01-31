# Cleaning up git history

You have two options.

## Option A: One new commit (keep existing history)

Stage the current reorganization and commit with the draft message:

```bash
git add -A
git commit -F COMMIT_MSG
git push origin main
```

History will still contain the old "adding files" / "adding more files" commits, plus this one clean message.

## Option B: Squash into two clean commits (rewrite history)

Result: **init** → **PiFM: Raspberry Pi FM radio receiver** (one commit with the full project).

1. Run the cleanup script from repo root:

   ```bash
   chmod +x scripts/cleanup-git-history.sh
   ./scripts/cleanup-git-history.sh
   ```

2. Push (rewrites `main` on the remote):

   ```bash
   git push --force-with-lease origin main
   ```

Use **Option B** only if you're okay force-pushing and no one else is relying on the current history.
