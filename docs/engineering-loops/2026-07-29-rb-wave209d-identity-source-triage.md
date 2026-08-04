# RB Wave209-D: identity/source-route triage

Wave209-D is a read-only, fail-closed triage of exactly 120 remaining Wave208
candidates: unresolved industrial cells (54), unresolved other (33), one
replacement, Восток (9), Contact (7), General Security (8), Security Force
(5), Alarm Force (2), and Optimus (1).

The output preserves an exact legacy model token where the title contains one,
the complete parenthetical product/pack form, a bounded likely first-party
route, scope exclusion, in-wave duplicates, and collisions from both the
complete canonical registry and the current Docker PostgreSQL product list.
It never promotes a claimed brand/model into an identity: every row has
`safe_to_apply=false`.

The builder proves the 120-row union and unique external IDs and proves zero
intersection with the declarative Wave209-A (APC/EnerSys/Sonnenschein),
Wave209-B (Delta/Fiamm/Leoch), and Wave209-C remaining assigned clusters.
No web request or database mutation is made; the Docker query is a `SELECT`
snapshot only.

Verification:

- `python scripts/build-rb-wave209d-identity-source-triage.py`
- `python -m pytest scripts/tests/test_wave209d_identity_source_triage.py`
