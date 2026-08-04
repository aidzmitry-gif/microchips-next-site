<?php

namespace Tests\Feature;

use Illuminate\Support\Facades\DB;
use Tests\TestCase;

class TestingDatabaseIsolationTest extends TestCase
{
    public function test_phpunit_forces_an_isolated_in_memory_sqlite_database(): void
    {
        $this->assertSame('testing', app()->environment());
        $this->assertSame('sqlite', DB::connection()->getDriverName());
        $this->assertSame(':memory:', config('database.connections.sqlite.database'));
        $this->assertNotSame('pgsql', config('database.default'));
    }
}
