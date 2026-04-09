---
mode: agent
description: "Run full git push workflow: stage, quality gates, professional English Conventional Commit, and push."
tools: ["run_in_terminal"]
---

When invoked, execute a full push workflow in the current repository:

1. Detect current branch.
2. Stage all changes (`git add .`).
3. Check staged changes (`git diff --cached --name-status`).
4. If no staged changes, stop and report that there is nothing to commit.
5. Run required quality gates in this order with safe defaults:
   - Tests: `pytest`
   - Lint: `python -m ruff check .`
   - Build: `python -m compileall Src`
   If one fails, stop and report the failing gate.
6. Build a professional English commit message using Conventional Commits with scope.
   - Infer `type` and `scope` from changed files when possible.
   - If uncertain, use `fix(core): <professional title>`.
   - Keep title concise and professional.
   - Add body explaining why and impact.
7. Commit with the generated message.
8. Push to origin with upstream: `git push -u origin <current-branch>`.
9. Return a short summary with branch, commit hash, and pushed files.

Message policy:
- Always in professional English.
- Use Conventional Commit format with scope: `<type>(<scope>): <title>`.
- Do not ask unnecessary follow-up questions.
