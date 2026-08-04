# Wave225-B: local-image OCR review helper

`scripts/review-image-ocr-batch.ps1` is a Windows PowerShell 5.1 review aid for local product-image manifests. It uses the installed Windows.Media.Ocr engines for both `en-US` and `ru-RU`; it does not call a web service, a Laravel command, or a database.

Input CSV must be UTF-8 and contain `image_path` plus exactly one of `expected_mpn` or `expected_model_core` on every row. The expectation comes only from that CSV field, never from the filename. Example:

```csv
image_path,expected_mpn,expected_model_core
C:\review\ER14505H.png,ER14505H,
C:\review\BR-2-3A.png,,BR-2/3A
```

Run it in Windows PowerShell 5.1:

```powershell
.\scripts\review-image-ocr-batch.ps1 -ManifestPath ".\docs\audits\generated\ocr-input.csv" -OutputPath ".\docs\audits\generated\ocr-review.csv"
```

The result is deterministic UTF-8-with-BOM CSV with the local image path, supplied expectation, SHA-256 of the combined OCR text, normalized OCR token sequence, selected languages, and only `PASS` or `HOLD`. `PASS` requires the full normalized expected token sequence to occur contiguously and with token boundaries in OCR text. Any missing file, undecodable image, unavailable OCR language, empty/invalid expectation, or non-match produces `HOLD`.

OCR is evidence for human image review, not identity proof: blurred labels, stylized fonts, rotations, low resolution, partial crops, confusable Cyrillic/Latin characters, and OCR language-pack availability can all produce false holds. A `PASS` must still be reviewed before any later, separately authorized action. The helper never infers a model, mutates data, stages content, publishes media, or performs an automatic approval.

## Verified Wave225 run

The PowerShell 5.1 bridge explicitly closes the generic `AsTask<TResult>(IAsyncOperation<TResult>)` method by the result type from each WinRT API signature; COM-backed WinRT operations do not expose that generic interface to PowerShell reflection. A real raster smoke used `.tmp/wave225-assets/1993.png` and completed decode plus recognition.

The full `rb-wave225-ocr-input.csv` run produced `rb-wave225-ocr-review.csv` with 125 rows: 48 `PASS` and 77 `HOLD`. All 77 holds have the conservative reason `exact_bounded_expected_token_sequence_not_found`; there are no bridge, decoder, missing-file, or language errors. The result CSV is UTF-8 with BOM.
