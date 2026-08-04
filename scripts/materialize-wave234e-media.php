<?php

declare(strict_types=1);

if ($argc !== 4) {
    fwrite(STDERR, "Usage: php materialize-wave234e-media.php candidates.csv storage-root output-dir\n");
    exit(2);
}

[$script, $csvPath, $storageRoot, $outputDir] = $argv;
$handle = fopen($csvPath, 'rb');
if ($handle === false) {
    fwrite(STDERR, "Candidate CSV is unreadable.\n");
    exit(1);
}
$header = fgetcsv($handle, 0, ',', '"', '');
if ($header === false) {
    fwrite(STDERR, "Candidate CSV has no header.\n");
    exit(1);
}
$columns = array_flip($header);
foreach (['storage_path', 'content_sha256'] as $required) {
    if (! isset($columns[$required])) {
        fwrite(STDERR, "Candidate CSV misses {$required}.\n");
        exit(1);
    }
}
if (! is_dir($outputDir) && ! mkdir($outputDir, 0777, true) && ! is_dir($outputDir)) {
    fwrite(STDERR, "Unable to create output directory.\n");
    exit(1);
}

$copied = 0;
while (($row = fgetcsv($handle, 0, ',', '"', '')) !== false) {
    $relative = trim((string) $row[$columns['storage_path']]);
    $expectedHash = strtolower(trim((string) $row[$columns['content_sha256']]));
    if ($relative === '' || str_contains($relative, '..') || str_starts_with($relative, '/')
        || preg_match('~^[A-Za-z]:[\\/]~', $relative) === 1
        || preg_match('/^[a-f0-9]{64}$/', $expectedHash) !== 1) {
        fwrite(STDERR, "Unsafe candidate path or hash: {$relative}.\n");
        exit(1);
    }
    $source = rtrim($storageRoot, '/\\').DIRECTORY_SEPARATOR.str_replace(['/', '\\'], DIRECTORY_SEPARATOR, $relative);
    if (! is_file($source) || hash_file('sha256', $source) !== $expectedHash) {
        fwrite(STDERR, "Pinned media is missing or hash-mismatched: {$relative}.\n");
        exit(1);
    }
    $destination = rtrim($outputDir, '/\\').DIRECTORY_SEPARATOR.str_replace(['/', '\\'], DIRECTORY_SEPARATOR, $relative);
    $destinationDirectory = dirname($destination);
    if (! is_dir($destinationDirectory)
        && ! mkdir($destinationDirectory, 0777, true)
        && ! is_dir($destinationDirectory)) {
        fwrite(STDERR, "Unable to create destination directory for {$relative}.\n");
        exit(1);
    }
    if (! copy($source, $destination)) {
        fwrite(STDERR, "Unable to copy {$relative}.\n");
        exit(1);
    }
    $copied++;
}
fclose($handle);

fwrite(STDOUT, json_encode(['copied' => $copied, 'hash_verified' => $copied], JSON_UNESCAPED_SLASHES).PHP_EOL);
