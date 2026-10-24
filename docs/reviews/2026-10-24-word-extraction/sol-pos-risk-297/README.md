# POS-risk lexical-pair decisions (agent review)

This frozen research judgment covers the 297 old `word`/`compound` pairs reproducibly flagged by particles, multiple verbs/adjectives, auxiliary morphology, or symbols on either selected surface. The old 307 count was an exploratory estimate; 297 is the actual population under the recorded selection rule. These judgments are not researcher approval and are not an applied data patch.

| Artifact | SHA-256 |
| --- | --- |
| Input `../pair-level-audit.csv` | `dfb4d25499d4a4637f8c1d5ec44612fc7ae92d60f15c765b1ba5ac565044d152` |
| `classify_lexical_pos_risks.py` | `80caf891923465caa6f88c1727b69237f75cd2340f61267a513a6d196c31295c` |
| `lexical-pos-risk-sol-decisions.json` | `d68c7f6232fe0a9d07dda3ed689e205cdf9e37e4a3f3158f16ccd686fb996d52` |

Decisions: KEEP_LEXICAL 99, RETYPE_LEXICAL 3, RETYPE_CONTEXTUAL 132, SHORTEN 59, SHORTEN_MULTI 3, EXPAND_CONTEXTUAL 1, NEED_SOURCE 0. Each JSON item records the old PairID, OriginalHash, surfaces, bounds, POS evidence, and a decision reason. Shortening is a boundary decision only: new readings require source-backed or uniquely aligned old-review evidence before confirmation. The data migration must compare each old signature against the current canonical review and log already-applied or superseded cases instead of replaying them.

## Individual strict-gate exceptions

Of the 49 previously unapplied SHORTEN candidates, one passed the strict machine gate and 48 were held. `pos-shortener-sol-exceptions-48.json` records a source-cited individual adjudication for each held PairID, exact new bounds/readings, and why the strict gate fails. Forty have only side-specific source parentheses (pronunciation, sense, place, or referent notes) outside the chosen spoken lexical surface; eight have old reviewed readings segmentable using the preserved primary excerpt and lexical references. These are finite exceptions, not a change to the automatic gate. Meanings, qualifiers, uncertain readings, immutable originals, and lineage must survive the data patch; the engine must still validate every whole record. Two subtypes are corrected to `compound` (`最終財/最終材`, `投開票/東海地方`).

| Artifact | SHA-256 |
| --- | --- |
| Gate input `../pos-shortener-verified-1/gate-rejections.json` | `10f44b299fe65ec544e12b056e8a35fc45b006ec3fdd11d478b18c5b281238f3` |
| `build_pos_shortener_sol_exceptions.py` | `2591d40ae57e5cfeee07b8be30fd59cb36b4cf4b42fb0d302779da61e0632e8c` |
| `pos-shortener-sol-exceptions-48.json` | `397b7f86f16d0bc2d6c1d72cae0dd15f463782e79ba7d3beeabe01a7f1bf128a` |
