<?php

namespace App\Domain\Imports;

final class OneCNomenclatureClassifier
{
    /**
     * Classification is deliberately advisory. No row becomes publishable here.
     *
     * @return array{status: string, flags: list<string>}
     */
    public function classify(bool $isGroup, ?string $article, string $name): array
    {
        if ($isGroup) {
            return ['status' => 'source_group', 'flags' => []];
        }

        $flags = [];

        if (blank($article)) {
            $flags[] = 'missing_article';
        } elseif ($this->looksLikeStorageLocation($article)) {
            $flags[] = 'article_looks_like_storage_location';
        }

        if ($this->looksLikeNonProduct($name)) {
            $flags[] = 'suspected_non_product';
        }

        $status = match (true) {
            in_array('suspected_non_product', $flags, true) => 'needs_catalog_classification',
            in_array('missing_article', $flags, true) => 'needs_identity_review',
            in_array('article_looks_like_storage_location', $flags, true) => 'needs_article_review',
            default => 'needs_catalog_review',
        };

        return ['status' => $status, 'flags' => $flags];
    }

    private function looksLikeStorageLocation(string $article): bool
    {
        $value = trim($article);

        return preg_match('/^\p{L}\d(?:\.\d+){2,}\.?$/u', $value) === 1;
    }

    private function looksLikeNonProduct(string $name): bool
    {
        return preg_match(
            '/(?:доставк|товарн\w*\s+накладн|книг\w*\s+замечан|\bбсо\b|\bуслуг\w*)/iu',
            $name
        ) === 1;
    }
}
