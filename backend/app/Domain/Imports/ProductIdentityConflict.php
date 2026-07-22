<?php

namespace App\Domain\Imports;

use DomainException;

class ProductIdentityConflict extends DomainException
{
    /**
     * @param  list<int>  $productIds
     */
    public function __construct(
        public readonly string $matchKey,
        public readonly array $productIds,
        string $message,
    ) {
        parent::__construct($message);
    }
}
