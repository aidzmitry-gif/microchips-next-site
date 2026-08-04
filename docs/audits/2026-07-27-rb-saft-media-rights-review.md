# RB Saft model-core media and rights review

Date: 2026-07-27  
Scope: `docs/imports/rb-source-backed-description-drafts-saft-model-core-wave-79-2026-07-27.json`  
Mode: read-only source review; no image was downloaded, mirrored, transformed or applied.

## Decision

**Release blocker:** do not download, mirror, crop, hotlink or publish any Saft
image until Microchips has written permission from Saft, or a verifiable
distributor/media licence that explicitly permits commercial website use.

Official hosting and a Saft photo credit establish provenance, but do not grant
reuse rights. Section 5 of the
[Saft4U General Terms and Conditions of Use](https://saft4u.saft.com/general-terms-and-conditions-use)
states that no licence is granted beyond viewing and that non-private
reproduction requires prior express authorization. Section 6.2 also requires
prior written consent for hyperlinks to the website. Consequently neither
copying the files to Microchips storage nor using the Saft URLs as remote image
sources is approved by this review.

## Wave coverage

The manifest contains 50 catalogue rows grouped into eight exact model cores:

| Model core | Rows | Official datasheet |
|---|---:|---|
| LS14250 | 8 | [Saft LS14250 datasheet](https://saft4u.saft.com/en/download_file/133c84de-f6e9-46b6-a412-fc4ed453fb5c/English) |
| LS14500 | 13 | [Saft LS14500 datasheet](https://saft4u.saft.com/en/download_file/738dfd7b-3131-4e31-8924-401cd9a36bbc/English) |
| LS17330 | 8 | [Saft LS17330 datasheet](https://saft4u.saft.com/en/download_file/da7e4f7d-920b-46c7-bce2-5febf9abe7d1/English) |
| LS17500 | 6 | [Saft LS17500 datasheet](https://saft4u.saft.com/fr/download_file/6fbdd60f-bba6-4f67-81a0-85ce1b412664/English) |
| LS26500 | 6 | [Saft LS26500 datasheet](https://saft4u.saft.com/en/download_file/e9a98622-3564-4570-bca2-d6ce1504589a/English) |
| LS33600 | 5 | [Saft LS33600 datasheet](https://saft4u.saft.com/en/download_file/5241def1-8668-4a68-9d2e-820bd3c68589/English) |
| LSH14 | 2 | [Saft LSH14 datasheet](https://saft4u.saft.com/fr/download_file/e45bd03f-3674-4eeb-bd5d-431d53253df1/English) |
| LSH20 | 2 | [Saft LSH20 datasheet](https://saft4u.saft.com/en/download_file/8bdd6f76-c9c5-422e-95bd-a18e0a12d80f/English) |
| **Total** | **50** | **8 model-core sources** |

The official datasheets contain exact-model imagery and identify the photo
credit as `© Saft`. They are the authoritative model-core evidence containers,
but extraction of an embedded photograph would create a new copy and remains
blocked by the rights decision above.

## Direct official-hosted image candidates

The following static URLs were found on official Saft pages and returned HTTP
200 during the review:

| Coverage | Direct asset | Official source page | Evidence quality |
|---|---|---|---|
| LS/LSH/LSP family | [Packshot-LS-LSH.JPG](https://saft4u.saft.com/sites/default/files/Packshot-LS-LSH.JPG) | [LS, LSH, LSP product family](https://saft4u.saft.com/en/product/ls-lsh-lsp) | Manufacturer-hosted family packshot; not an exact SKU or connector image. |
| LS14250 | [ls14250_saft_batterie.jpg](https://saft.com/sites/default/files/paragraphs_item/standard_text/editor/ls14250_saft_batterie.jpg) | [Xtel Wireless case study](https://saft.com/en/case-studies/xtel-wireless-moves-iot-solutions-and-trusts-saft-batteries-power-their-versatile) | Manufacturer-hosted base-cell image; exact connector/terminal is not evidenced. |
| LS14500 | [saft_battery_ls14500_0.jpg](https://saft.com/sites/default/files/paragraphs_item/standard_text/editor/saft_battery_ls14500_0.jpg) | [BumbleBee sensors case study](https://saft.com/en/case-studies/saft-batteries-powering-bumblebee-sensors-wireless-monitoring-iot-solution-optimize-0) | Manufacturer-hosted base-cell image; exact connector/terminal is not evidenced. |

An additional LS14250 contextual image exists at
[ls14250_saft_batteries_for_iot_sensors.png](https://saft.com/sites/default/files/paragraphs_item/standard_text/editor/ls14250_saft_batteries_for_iot_sensors.png),
but it is an application/context image rather than a preferred catalogue
packshot.

No standalone official original image URL was exposed for LS17330, LS17500,
LS26500, LS33600, LSH14 or LSH20. The exact-model images inside their official
datasheets must not be extracted without permission.

Official-hosted means that Saft publishes the asset on its domain. It does not
prove that Saft owns every case-study photograph rather than using it under a
third-party licence. The datasheet `© Saft` photo credit is stronger ownership
evidence, but still does not grant Microchips a licence.

## Variant accuracy assessment

The 50 manifest rows were conservatively classified from their supplied names:

| Presentation class | Rows | Media consequence |
|---|---:|---|
| Base model, exact execution unspecified | 7 | A model-core image can be representative after rights clearance. |
| Connector, terminal, wire or suffix variant | 33 | A base-cell image cannot be presented as the exact execution. |
| Multi-cell bundle or kit | 10 | A single-cell image is materially misleading; require an exact bundle image or keep the placeholder. |

After written rights clearance, one base-model photograph may be shared across
the 33 connector/terminal variants only under all of these controls:

1. Store the media identity scope as `model_core`, never `exact_product`.
2. Display a visible caption such as: `Фото базового элемента Saft LS14500;
   выводы, разъём и комплектация могут отличаться.`
3. Use neutral alt text naming only the base model; do not mention a connector,
   terminal, wire, country, kit quantity or assembly configuration.
4. Keep any exact-image verification flag false and do not emit the shared
   image as evidence of an exact variant in structured data.
5. Do not use the single-cell photograph for the 10 bundle rows.

## Required unblock evidence

Before any candidate becomes publishable, retain one of the following in the
project evidence registry:

- written Saft permission identifying the permitted assets, markets, domains,
  transformations, attribution and duration; or
- a distributor/media agreement granting equivalent commercial reuse rights,
  with evidence that the licensor is authorized to grant them.

Until that evidence exists, the existing placeholder remains the only safe
catalogue presentation for all 50 rows.
