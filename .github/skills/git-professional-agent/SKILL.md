---
name: git-professional-agent
description: 'Professional Git workflow with mandatory quality gates (tests, lint, build), Conventional Commits with required scope, optional breaking-change support, and push to origin. Use when you want high-quality, professional English commit messages and safe delivery.'
argument-hint: 'Intent, e.g. "fix sr vf loading" or "feat export pipeline"'
user-invocable: true
---

# Git Professional Agent

## What This Skill Produces
- A validated branch target (current, existing, or newly created)
- Staged changes with visibility of affected files
- Mandatory quality checks pass: tests, lint, and build
- A Conventional Commit message in professional English with required scope
- Optional breaking-change notation (`!` and `BREAKING CHANGE:` footer)
- A commit pushed to `origin/<branch>`
- Early exit when there are no staged changes

## When To Use
- You finished a coding task and want a clean commit workflow
- You want to enforce Conventional Commits consistently
- You want to avoid forgetting `git push -u origin <branch>`
- You want a repeatable, guided release/check-in routine

## Procedure
1. Detect current branch.
2. Ask user to confirm current branch or provide another branch name.
3. If a different branch is requested:
   - Try `git checkout -b <branch>`.
   - If branch already exists, fallback to `git checkout <branch>`.
4. Stage changes with `git add .`.
5. Read staged changes via `git diff --cached --name-status`.
6. If no staged changes exist, stop with a clear message.
7. Display modified files list.
8. Ask and run mandatory quality gates in this order:
  - Test command
  - Lint command
  - Build command
  - Abort immediately if any command fails.
9. Ask for Conventional Commit type:
   - `feat`, `fix`, `refactor`, `docs`, `chore`
10. Ask for commit scope (required), e.g. `sr`, `cgf`, `pmpv-ui`.
11. Ask whether this is a breaking change.
12. Ask for commit title in professional English (required).
13. Ask for optional commit body in professional English.
14. Build final commit message:
  - Standard: `<type>(<scope>): <title>`
  - Breaking: `<type>!(<scope>): <title>`
  - With body:
    - `<type>(<scope>): <title>` or `<type>!(<scope>): <title>`
     - blank line
     - `<body>`
  - If breaking: append `BREAKING CHANGE: <impact summary>` footer.
15. Commit using message file/stdin mode (`git commit -F -`).
16. Push with upstream tracking:
   - `git push -u origin <branch>`
17. Print a success summary.

## Decision Points
- Branch decision:
  - If user input is empty, keep current branch.
  - If input differs, create/switch branch.
- Quality gates:
  - If tests/lint/build fail, abort before commit.
- Change detection:
  - If staged diff is empty, abort safely.
- Scope:
  - Required. Must be a short, lowercase identifier (letters, numbers, hyphen).
- Breaking change:
  - If yes, use `!` in header and add `BREAKING CHANGE:` footer.

## Completion Checks
- Branch after switch is the requested branch.
- `git diff --cached --name-status` is non-empty before commit.
- Tests command exits with code 0.
- Lint command exits with code 0.
- Build command exits with code 0.
- Commit subject follows Conventional Commit format with scope.
- Push completes to `origin` with upstream (`-u`).

## Quality Criteria
- Commit type matches intent (`feat`/`fix`/`refactor`/`docs`/`chore`).
- Scope is specific and consistent with touched modules.
- Title is clear, action-focused, and professional English.
- Body explains why and impact (not only what changed), in professional English.
- No hidden local-only branch state after push.

## Failure Handling
- Branch create failure: fallback to checkout existing branch.
- No changes: exit without creating empty commit.
- Test/lint/build failure: stop and report the failing gate.
- Push failure: report remote/auth/network issue and keep commit local.

## Script
- Run [Git Pro script](./scripts/git-professional-agent.sh) when shell environment supports Bash.
