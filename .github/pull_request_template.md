# Pull Request Template

## Description
Please include a summary of the changes and the related issue. Explain the motivation for the change and any relevant context.

## Checklist
- [ ] I have read the contributing guidelines.
- [ ] I have added necessary files.
    - [ ] `mishearing/<your-data>.csv`
    - [ ] `environment/<your-data>.csv`
    - [ ] `tag/<your-data>.csv`
- [ ] I have run `frictionless validate` locally and ensured all checks pass.
- [ ] I have added tests that prove my fix is effective or that my feature works.
- [ ] I have added necessary documentation (if applicable).
- [ ] I have made web archive and added the link to the `README.md`.

## Pair extraction / annotation changes (if applicable)
- [ ] Added regression tests before changing extraction or annotation behavior.
- [ ] Generated machine drafts and inspected all candidates, including zero-candidate records.
- [ ] Applied actual source-grounded corrections; recorded reviewer, evidence and original hashes.
- [ ] Reported counts: input __ / reviewed __ / pending __ / excluded __ / unprocessed __.
- [ ] Ran `make pairs-test`, `make pairs-check`, and `make api-check` locally.
- [ ] For an evaluation release, `check --require-complete` passes; pending cases are explicitly excluded.
- [ ] Preserved historical research snapshots and identified the new data version/change log.
- [ ] Listed remaining researcher questions; did not equate structural validation with linguistic correctness.

## Related Issues
Link any related issues here.

## Additional Notes
Add any additional information or context here.
