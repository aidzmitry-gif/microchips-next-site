<?php

namespace Tests;

use Illuminate\Foundation\Testing\TestCase as BaseTestCase;

abstract class TestCase extends BaseTestCase
{
    protected function setUp(): void
    {
        parent::setUp();

        $this->withHeader('X-Lead-Proxy-Secret', 'testing-lead-proxy-secret-32-characters');
    }
}
