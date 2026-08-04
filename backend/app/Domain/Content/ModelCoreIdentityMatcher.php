<?php

namespace App\Domain\Content;

use App\Domain\Imports\ProductIdentity;

final class ModelCoreIdentityMatcher
{
    /** @var list<string> */
    private const ALLOWED_ATTACHED_SUFFIXES = [
        'cna',
        'cnr',
        'fl',
        'fle',
        'estd',
        '2pf',
        '3pf',
        '4pf',
    ];

    public static function nameContains(string $name, string $modelCore): bool
    {
        $normalizedCore = self::normalizeLookalikes($modelCore);
        if ($normalizedCore === null) {
            return false;
        }

        preg_match_all('/[\p{L}\p{N}]+/u', mb_strtolower($name), $matches);
        $tokens = array_values(array_filter(array_map(
            self::normalizeLookalikes(...),
            $matches[0] ?? [],
        )));

        foreach ($tokens as $start => $token) {
            $candidate = '';
            for ($offset = $start, $count = count($tokens); $offset < $count; $offset++) {
                $candidate .= $tokens[$offset];
                if ($candidate === $normalizedCore) {
                    return true;
                }
                if (str_starts_with($candidate, $normalizedCore)) {
                    return in_array(substr($candidate, strlen($normalizedCore)), self::ALLOWED_ATTACHED_SUFFIXES, true);
                }
                if (strlen($candidate) >= strlen($normalizedCore)) {
                    break;
                }
            }
        }

        return false;
    }

    public static function nameEndsWith(string $name, string $exactModel): bool
    {
        $nameTokens = self::normalizedTokens(self::withoutTrailingTechnicalSummary($name));
        $modelTokens = self::normalizedTokens($exactModel);
        if ($modelTokens === [] || count($nameTokens) < count($modelTokens)) {
            return false;
        }

        return array_slice($nameTokens, -count($modelTokens)) === $modelTokens;
    }

    private static function withoutTrailingTechnicalSummary(string $name): string
    {
        $technology = '(?:VRLA\s+)?(?:AGM|GEL|LiFePO4)';
        $value = '\d+(?:[.,]\d+)?\s*(?:Ah|A\x{00B7}h|\x{0410}\x{00B7}\x{0447}|V|\x{0412})';
        $pattern = '/\s*\(\s*'.$technology.'(?:\s*,\s*'.$value.'){1,2}\s*\)\s*$/iu';

        return preg_replace($pattern, '', $name) ?? $name;
    }

    /** @return list<string> */
    private static function normalizedTokens(string $value): array
    {
        preg_match_all('/[\p{L}\p{N}]+/u', mb_strtolower($value), $matches);

        return array_values(array_filter(array_map(
            self::normalizeLookalikes(...),
            $matches[0] ?? [],
        )));
    }

    private static function normalizeLookalikes(mixed $value): ?string
    {
        $normalized = ProductIdentity::normalize($value);
        if ($normalized === null) {
            return null;
        }

        return strtr($normalized, [
            'а' => 'a',
            'с' => 'c',
            'е' => 'e',
            'о' => 'o',
            'р' => 'p',
            'х' => 'x',
        ]);
    }
}
