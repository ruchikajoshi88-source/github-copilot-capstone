Generate a production-ready Pull Request description based on the current git diff:

## Summary
Provide a 2-3 sentence overview of what was built and why.

## Changes Made
A bulleted list of all files added or modified, detailing the reason for each change.

## Test Evidence
Verification summary including pytest results, coverage reports, and happy/edge case runs.

## Known Limitations
List any components marked as 'Not Found', partial implementations, or out-of-scope items.

## Reviewer Checklist
- [ ] Requirements from requirements.md verified
- [ ] Architecture patterns followed
- [ ] No hardcoded secrets
- [ ] Error handling and idempotency verified
- [ ] Unit and integration tests passing
