---
mode: agent
description: "Production-grade Git workflow automation: intelligent staging, Conventional Commits with scope inference, upstream push with optional GitHub/GitLab pull request creation. Invoke as '/push' for standard push or '/push+pr' to open a PR after push."
tools: ["run_in_terminal"]
tags: ["git", "automation", "devops", "ci-cd", "conventional-commits"]
---

# Git Push & Pull Request Automation

## Overview

This agent executes a fully automated, production-ready Git workflow with zero manual intervention. It enforces Conventional Commits, validates repository state before every operation, and produces a structured audit report on completion.

| Command     | Behavior                                                   |
| ----------- | ---------------------------------------------------------- |
| `/push`     | Stage → Commit (Conventional) → Push with upstream set    |
| `/push+pr`  | All of the above + create and open a Pull Request          |

---

## Execution Pipeline

### Phase 1 — Repository State Validation

Run all checks before touching any files:

```bash
git rev-parse --abbrev-ref HEAD          # Resolve active branch
git status --porcelain                   # Detect working-tree state
git diff --check                         # Abort on conflict markers
git stash list                           # Surface hidden stashed work
```

**Abort conditions** (hard stop, no commit attempted):
- Unresolved merge/rebase conflict markers detected (`git diff --check` exits non-zero)
- Repository is in a detached HEAD state
- Remote `origin` is unreachable

**Advisory warnings** (proceed after surfacing to user):
- Protected branch detected (`main`, `master`, `release/*`, `production`)
- Stash entries exist that may conflict with staged changes
- Binary files (`.png`, `.pdf`, `.exe`, `.zip`, etc.) are staged

---

### Phase 2 — Staging & Change Analysis

```bash
git add .
git diff --cached --name-status          # Enumerate all staged changes
git diff --cached --stat                 # Line-level diff statistics
```

Categorize every staged file into one of:

| Category    | Example Paths                              |
| ----------- | ------------------------------------------ |
| `backend`   | `backend/`, `api/`, `server/`              |
| `frontend`  | `frontend/`, `Src/`, `assets/`, `Views/`   |
| `etl`       | `etl/`, `pipeline/`, `extractors/`         |
| `database`  | `Database/`, `migrations/`, `*.sql`        |
| `config`    | `*.yaml`, `*.yml`, `*.toml`, `*.env`       |
| `ci`        | `.github/`, `.gitlab-ci.yml`, `Dockerfile` |
| `test`      | `tests/`, `test_*.py`, `*.spec.*`          |
| `docs`      | `*.md`, `*.rst`, `docs/`                   |
| `core`      | Root-level files or unclassified paths     |

---

### Phase 3 — Conventional Commit Generation

**Commit format (strict)**:

```
<type>(<scope>): <imperative-title>

[optional body — required if changes > 3 files or any file > 100 lines modified]

[optional footer — issue references, breaking changes]
```

#### Type Inference Matrix

| Type        | Trigger Signals                                              |
| ----------- | ------------------------------------------------------------ |
| `feat`      | New files added (`A`), new modules, new endpoints           |
| `fix`       | Modified files in `Services/`, `bug`, `fix`, `patch` in name|
| `refactor`  | Renamed/moved files (`R`), structural reorganization         |
| `perf`      | Changes in query files, caching layers, batch processors     |
| `test`      | Files in `tests/`, prefixed `test_`, suffixed `.spec`        |
| `ci`        | Files in `.github/`, `Dockerfile`, `docker-compose.*`        |
| `docs`      | `.md`, `.rst`, `README`, `CHANGELOG`                        |
| `style`     | Formatters, linters, whitespace-only diffs                  |
| `chore`     | `requirements.txt`, `package.json`, lock files, config-only |

#### Scope Inference Rules

1. Map the dominant file category (by file count) to a scope token.
2. If changes span ≥ 3 distinct categories, use `core`.
3. Never omit scope — use `core` as the last-resort fallback.

#### Title Rules

- Imperative mood, present tense: `add`, `fix`, `remove`, `update`, `refactor`
- Max 50 characters, all lowercase (except proper nouns and acronyms)
- No trailing period
- Must convey **what changed and why** in one phrase

#### Body Rules (triggered when > 3 files changed or any file > 100 lines modified)

```
- WHY: Explain the business or technical motivation
- WHAT: Describe the solution approach
- IMPACT: Note downstream effects on pipelines, APIs, or dependent modules
- REFS: Fixes #<id> | Related to #<id> | Closes #<id>
```

**Well-formed commit example**:

```
feat(etl): add automated data quality checks for staging layer

- Integrated validation pipeline using configurable rule sets in dq_config.yaml
- Covers format validation, range checks, and referential integrity against warehouse
- Failures trigger alerter.py notifications and block downstream DAG execution

Fixes #112
```

---

### Phase 4 — Commit & Push

Execute in sequence; abort the pipeline if any command exits non-zero:

```bash
git commit -m "<generated-message>"
git push -u origin <current-branch>
```

Capture and display:
- Abbreviated commit SHA (`git rev-parse --short HEAD`)
- Full push output for traceability
- Upstream tracking confirmation

---

### Phase 5 — Pull Request Creation *(invoked only with `/push+pr`)*

#### Platform Detection

```bash
git remote get-url origin
```

| URL Pattern                   | Platform  | CLI Tool     |
| ----------------------------- | --------- | ------------ |
| `github.com`                  | GitHub    | `gh pr create` |
| `gitlab.com` / self-hosted GL | GitLab    | `glab mr create` |
| Other                         | Generic   | Display URL  |

#### PR Metadata Generation

| Field         | Strategy                                                         |
| ------------- | ---------------------------------------------------------------- |
| **Title**     | Reuse commit title verbatim                                      |
| **Body**      | Commit body + auto-generated checklist (tests, docs, review)     |
| **Base**      | Default branch (`main` / `master`) auto-detected from remote     |
| **Labels**    | Mapped from commit type: `feat→enhancement`, `fix→bug`, etc.    |
| **Assignees** | Derived from CODEOWNERS if present; otherwise omit               |

#### Auto-generated PR Body Template

```markdown
## Summary
<!-- Auto-populated from commit body -->

## Changes
<!-- Bullet list of staged files by category -->

## Checklist
- [ ] Tests added or updated
- [ ] Documentation updated
- [ ] No secrets or credentials committed
- [ ] CI pipeline passes locally
```

---

## Output Report

Emit this exact structure on successful completion:

```
╔═══════════════════════════════════════════════════╗
║           GIT PUSH WORKFLOW — COMPLETE            ║
╠═══════════════════════════════════════════════════╣
║  Branch       │ <branch-name>                     ║
║  Commit SHA   │ <short-sha>                       ║
║  Message      │ <type>(<scope>): <title>           ║
║  Files        │ <N> changed  (+<additions> -<del>)║
║  Remote       │ origin → <remote-url>             ║
║  Upstream     │ ✓ Tracking set                    ║
╠═══════════════════════════════════════════════════╣
║  PR           │ <URL>  (only when /push+pr)       ║
╚═══════════════════════════════════════════════════╝
```

---

## Safety & Guardrails

| Rule                                         | Enforcement Level |
| -------------------------------------------- | ----------------- |
| Conflict markers present                     | ❌ Hard abort      |
| Pushing to `main`, `master`, `production`    | ⚠️ Warn + confirm  |
| Force-push required (`--force-with-lease`)   | ⚠️ Warn + confirm  |
| Binary files staged (images, archives, etc.) | ⚠️ Surface warning |
| Empty commit (nothing staged)                | ❌ Hard abort      |
| Remote unreachable before push               | ❌ Hard abort      |
| No meaningful commit message possible        | ❌ Hard abort      |

---

## Non-Interactive Execution Contract

- **No questions asked.** Apply sensible defaults for all inferred values.
- Stage all working-tree changes with `git add .` — no partial staging.
- For `/push+pr`, create the PR immediately after push without prompting.
- All reasoning and decisions must be captured in the output report.
- If a hard-abort condition is met, emit a clear `ABORTED` report with the exact reason and corrective action before stopping.
