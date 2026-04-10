---
mode: agent
description: "Execute professional Git workflow: stage changes, create Conventional Commits with intelligent scope detection, push with upstream tracking. Use '/push+pr' to automatically open a pull request on GitHub/GitLab after push."
tools: ["run_in_terminal"]
tags: ["git", "automation", "devops"]
---

# Professional Git Push & PR Workflow

## Core Behavior

When invoked as `/push`: Execute a complete, production-grade push workflow.
When invoked as `/push+pr`: Execute push workflow + automatically create pull request.

## Execution Steps

### Phase 1: Pre-flight Validation
1. **Branch Detection**: Identify current branch name with `git rev-parse --abbrev-ref HEAD`
2. **Status Check**: Run `git status --porcelain` to validate there are unstaged changes
3. **Stash Validation**: Warn if uncommitted changes exist but are not staged

### Phase 2: Staging & Analysis
1. **Stage All Changes**: Execute `git add .`
2. **Diff Analysis**: Run `git diff --cached --name-status` to categorize changes:
   - Parse filenames to intelligently infer commit `type` and `scope`
   - Group by functional areas (backend, frontend, db, config, etc.)
3. **Change Summary**: Display staged file count and types before proceeding

### Phase 3: Commit Generation
Build a professional, semantically meaningful commit message:

**Format**: `<type>(<scope>): <title>`

**Type inference** (from changed files):
- `feat` → New files, feature additions
- `fix` → Bugfixes, error corrections
- `refactor` → Code restructuring without logic change
- `perf` → Performance optimizations
- `docs` → Documentation-only changes
- `test` → Test additions or modifications
- `ci` → Pipeline/build configuration
- `style` → Formatting, linting (no code logic change)
- `chore` → Maintenance, dependencies

**Scope inference** (from file paths):
- Extract package/module name: `backend`, `frontend`, `etl`, `database`, `monitoring`, etc.
- If multiple scopes, use primary scope or `core`
- Default fallback: `core`

**Title requirements**:
- Imperative mood (e.g., "add", "fix", "improve", not "added", "fixed")
- Concise: max 50 characters
- Clear business value or technical rationale
- Lowercase (except proper nouns)

**Body requirements** (if changes exceed 3 files or single file >100 lines):
- Add blank line after title
- Explain **WHY** the change was made
- Describe **WHAT** problems it solves
- Note **IMPACT** on other systems if applicable
- Reference any tickets/issues: `Fixes #123` or `Related to #456`

**Example**:
```
feat(etl): add data quality checks for penalidade records

- Integrated Great Expectations framework for automated validation
- Validates format, ranges, and referential integrity
- Reduces manual review time by 40%

Fixes #89
```

### Phase 4: Commit & Push
1. **Commit**: Execute `git commit -m "<generated message>"`
2. **Push**: Execute `git push -u origin <current-branch>` with upstream tracking
3. **Verification**: Confirm push success and display commit hash

### Phase 5: Pull Request Creation (only with `/push+pr`)
1. **Platform Detection**: Identify Git hosting platform (GitHub, GitLab, Gitea)
2. **PR Template Generation**:
   - Title: Reuse commit title or enhance with context
   - Description: Auto-populate from commit body + checklist
   - Labels: Auto-tag by type and scope (e.g., `enhancement`, `backend`)
   - Assignees: Suggest based on changed files (if CODEOWNERS exists)
3. **Remote Validation**: Confirm push completed before creating PR
4. **Open in Browser**: Open PR URL in default browser for review

## Professional Standards

### Commit Message Policy
- **Language**: Always professional English (US spelling)
- **Format**: Strict Conventional Commits (no exceptions)
- **Scope**: Always present and meaningful
- **Tone**: Technical, clear, actionable
- **Grammar**: Complete sentences in body, imperative in title

### Code Quality
- Validate no merge conflicts before push
- Warn if pushing to `main` or `master` (require explicit confirmation)
- Auto-detect if force-push is needed (warn user)
- Preserve commit history integrity

### Output Report
Return structured summary:
```
═══════════════════════════════════════
✅ Push Workflow Complete
───────────────────────────────────────
Branch:        feature/data-quality-checks
Commit Hash:   a3f7e2c1 (abbreviated)
Message:       feat(etl): add data quality checks
Files Changed: 7 files (+245, -18 lines)
Remote:        origin
Status:        ✓ Pushed to upstream
───────────────────────────────────────
[PR Created] → <link> (if /push+pr)
═══════════════════════════════════════
```

## Safety Guardrails

- ❌ **Refuse** to push if there are unresolved merge conflicts
- ❌ **Refuse** to create commit without meaningful message
- ⚠️ **Warn** before force-pushing or pushing to protected branches
- ⚠️ **Warn** if committing binary files (unless intended)
- ✓ **Confirm** successful push before reporting completion

## Non-Interactive Execution

- Do not prompt for additional questions
- Use sensible defaults for type/scope when uncertain
- Assume user wants to push *all* staged changes
- For `/push+pr`, create PR with auto-generated title/description
- Log all decisions in output report
