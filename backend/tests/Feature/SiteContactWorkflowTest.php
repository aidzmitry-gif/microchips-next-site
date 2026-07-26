<?php

namespace Tests\Feature;

use App\Events\SiteContentChanged;
use App\Models\Site;
use App\Models\SiteContact;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Event;
use Illuminate\Validation\ValidationException;
use Tests\TestCase;

class SiteContactWorkflowTest extends TestCase
{
    use RefreshDatabase;

    public function test_contact_is_a_site_scoped_draft_by_default_and_is_not_in_the_published_scope(): void
    {
        $site = $this->site();
        $contact = SiteContact::create($this->contact($site));

        $this->assertFalse($contact->fresh()->is_published);
        $this->assertTrue($site->contacts()->whereKey($contact->id)->exists());
        $this->assertDatabaseCount('site_contacts', 1);
        $this->assertSame(0, SiteContact::query()->published()->count());
    }

    public function test_publication_requires_a_verifier_and_a_nonblank_verification_note(): void
    {
        $contact = SiteContact::create($this->contact($this->site()));

        try {
            $contact->publish(User::factory()->create(), ' ');
            $this->fail('Expected an empty verification note to be rejected.');
        } catch (ValidationException $exception) {
            $this->assertArrayHasKey('verification_note', $exception->errors());
        }

        $verifier = User::factory()->create();
        $contact->publish($verifier, 'Проверено по договору и действующему каналу связи.');

        $this->assertTrue($contact->fresh()->is_published);
        $this->assertSame($verifier->id, $contact->fresh()->verified_by);
        $this->assertNotNull($contact->fresh()->verified_at);
        $this->assertSame(1, SiteContact::query()->published()->count());
    }

    public function test_direct_published_save_without_a_complete_verification_tuple_is_rejected(): void
    {
        $payload = $this->contact($this->site());
        $payload['is_published'] = true;

        try {
            SiteContact::create($payload);
            $this->fail('Expected direct publication to be rejected.');
        } catch (ValidationException $exception) {
            $this->assertArrayHasKey('is_published', $exception->errors());
        }
    }

    public function test_changing_a_published_fact_revokes_publication_and_revalidation_is_dispatched(): void
    {
        Event::fake([SiteContentChanged::class]);
        $site = $this->site();
        $contact = SiteContact::create($this->contact($site));
        $contact->publish(User::factory()->create(), 'Проверено менеджером.');
        Event::fake([SiteContentChanged::class]);

        $contact->update(['value' => '+375 17 396 23 02']);

        $contact->refresh();
        $this->assertFalse($contact->is_published);
        $this->assertNull($contact->verified_at);
        $this->assertNull($contact->verified_by);
        $this->assertNull($contact->verification_note);
        Event::assertDispatched(SiteContentChanged::class, function (SiteContentChanged $event) use ($site): bool {
            return $event->site->is($site)
                && in_array('/contacts', $event->paths, true)
                && in_array('/sitemap.xml', $event->paths, true);
        });
    }

    /** @return array<string, mixed> */
    private function contact(Site $site): array
    {
        return [
            'site_id' => $site->id,
            'locale' => 'ru-BY',
            'city' => 'Минск',
            'type' => 'phone',
            'label' => 'Отдел продаж',
            'value' => '+375 33 347 75 10',
            'is_primary' => true,
        ];
    }

    private function site(): Site
    {
        return Site::create([
            'key' => 'microchips-by-'.uniqid(),
            'domain' => 'microchips-'.uniqid().'.test',
            'country_code' => 'BY',
            'currency_code' => 'BYN',
            'default_locale' => 'ru-BY',
            'name' => 'Microchips Беларусь',
        ]);
    }
}
