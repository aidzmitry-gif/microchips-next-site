# FANSO wave80 image-rights blocker — 2026-07-27

## Outcome

The official FANSO product pages expose primary gallery JPEGs for all nine
model cores represented by the 27 wave80 rows. These URLs are valid provenance
references, but they are **not publication assets**.

FANSO's official [Privacy / Rights statement](https://www.fansobattery.com/?list_72%2F780.html=)
states that rights in website images and other materials belong to FANSO and
that use requires express written consent. No such permission has been supplied
to this project.

Consequently:

- no FANSO image is retained locally;
- no StageSourceImageCandidates-compatible manifest is produced;
- no ProductMedia record may be created from these URLs;
- hotlinking, copying, editing and storefront publication remain blocked;
- the next allowed action is obtaining written commercial-use permission from FANSO.

## Technical observation before deletion

Nine unique official JPEG URLs returned HTTP 200 with `image/jpeg`. Each decoded
as an RGB JPEG at 560×422 pixels. Visual inspection showed bare cylindrical
model-core cells on white backgrounds; no cables or connectors were visible.
ER14335H, ER17505H and ER26500H images contain two views of the model and must
not be interpreted as two-unit packs.

These observations do not establish rights and do not prove `/S`, `/P`, `LD`,
`PF/PT`, connector, terminal, cable, pack, compatibility or origin variants.

## Reproducible blocked manifest

Run:

```powershell
python scripts/build-fanso-image-rights-blocked-manifest.py `
  docs/imports/rb-source-backed-description-drafts-fanso-model-core-wave-80-2026-07-27.json `
  docs/audits/generated/rb-blocked-fanso-model-core-image-rights-wave80-2026-07-27.json `
  --expected 27
```

The resulting JSON intentionally uses `blocked_candidates`, not `products`, and
sets `stage_source_image_candidates_compatible=false` so it cannot be passed to
the media staging command by mistake.
