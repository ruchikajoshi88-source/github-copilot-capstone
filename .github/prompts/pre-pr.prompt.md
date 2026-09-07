Run a pre-merge audit on the current branch:

1. Confirm all artifacts exist: requirements.md, architecture.md, design-review.md, impl-plan.md, review.md, verify.md, pr-description.md.
2. Verify all git changes are staged and cleanly formatted.
3. Confirm that pytest verification passes with 0 failures.
4. Prepare the final commit message following Conventional Commits (e.g., `feat(sdlc): ...`).
