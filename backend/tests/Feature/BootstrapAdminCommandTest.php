<?php

namespace Tests\Feature;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Hash;
use Tests\TestCase;

class BootstrapAdminCommandTest extends TestCase
{
    use RefreshDatabase;

    public function test_it_creates_exactly_one_first_admin_with_an_explicit_strong_password(): void
    {
        $this->artisan('admin:bootstrap', [
            'email' => 'OWNER@EXAMPLE.BY',
            '--name' => 'Platform owner',
            '--password' => 'correct-horse-battery-staple',
        ])
            ->expectsOutputToContain('First administrator created.')
            ->assertSuccessful();

        $admin = User::query()->sole();
        $this->assertSame('owner@example.by', $admin->email);
        $this->assertSame('Platform owner', $admin->name);
        $this->assertTrue($admin->is_admin);
        $this->assertTrue(Hash::check('correct-horse-battery-staple', $admin->password));
    }

    public function test_it_refuses_to_bootstrap_when_an_administrator_already_exists(): void
    {
        User::factory()->create(['is_admin' => true]);

        $this->artisan('admin:bootstrap', [
            'email' => 'second@example.by',
            '--password' => 'correct-horse-battery-staple',
        ])
            ->expectsOutputToContain('Refused: an administrator already exists.')
            ->assertFailed();

        $this->assertDatabaseCount('users', 1);
    }

    public function test_it_refuses_an_invalid_email_or_short_password_without_creating_a_user(): void
    {
        $this->artisan('admin:bootstrap', [
            'email' => 'not-an-email',
            '--password' => 'correct-horse-battery-staple',
        ])->assertFailed();
        $this->artisan('admin:bootstrap', [
            'email' => 'owner@example.by',
            '--password' => 'short',
        ])->assertFailed();

        $this->assertDatabaseCount('users', 0);
    }
}
