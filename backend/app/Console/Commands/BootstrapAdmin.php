<?php

namespace App\Console\Commands;

use App\Models\User;
use Illuminate\Console\Command;
use Illuminate\Support\Str;

class BootstrapAdmin extends Command
{
    protected $signature = 'admin:bootstrap
                            {email : Email address for the first administrator}
                            {--name= : Display name for the administrator}
                            {--password= : Password (use an interactive prompt whenever possible)}';

    protected $description = 'Create the first administrator on an empty deployment without seeding demo data';

    public function handle(): int
    {
        if (User::query()->where('is_admin', true)->exists()) {
            $this->error('Refused: an administrator already exists. Manage access through the existing administrator.');

            return self::FAILURE;
        }

        $email = Str::lower(trim((string) $this->argument('email')));
        if (filter_var($email, FILTER_VALIDATE_EMAIL) === false) {
            $this->error('A valid administrator email address is required.');

            return self::FAILURE;
        }

        $password = $this->option('password');
        if (! is_string($password) || $password === '') {
            if (! $this->input->isInteractive()) {
                $this->error('Refused: provide --password only for non-interactive automation.');

                return self::FAILURE;
            }

            $password = (string) $this->secret('Administrator password (minimum 16 characters)');
        }

        if (Str::length($password) < 16) {
            $this->error('Refused: the administrator password must contain at least 16 characters.');

            return self::FAILURE;
        }

        $name = trim((string) ($this->option('name') ?: Str::before($email, '@')));

        User::query()->create([
            'name' => $name === '' ? $email : $name,
            'email' => $email,
            'password' => $password,
            'is_admin' => true,
        ]);

        $this->info('First administrator created. Sign in at /admin and configure real site profiles before publishing any URL.');

        return self::SUCCESS;
    }
}
