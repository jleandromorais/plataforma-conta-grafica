# Push Shortcut

If the user message is exactly `Push` or `push`, treat it as a request to run the repository push workflow immediately.

Required behavior:
1. Stage all changes.
2. If there are no staged changes, report and stop.
3. Generate a professional English Conventional Commit message with mandatory scope.
4. Commit.
5. Push with upstream to current branch.

Output style:
- Keep responses concise.
- Always show the final branch, commit hash, and push status.
