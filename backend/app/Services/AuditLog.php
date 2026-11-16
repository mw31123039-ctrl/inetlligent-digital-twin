<?php

namespace App\Services;

use App\Models\AuditEvent;

/**
 * Records who did what to which record. Callers must pass only non-health metadata (counts, versions,
 * status values); free text, symptoms, anatomy and document content never belong here.
 */
class AuditLog
{
    /**
     * @param  array<string, scalar|null>  $meta
     */
    public function record(string $action, ?int $ownerId, ?int $actorId, ?string $targetType = null, ?string $targetId = null, array $meta = []): void
    {
        AuditEvent::create([
            'owner_id' => $ownerId,
            'actor_id' => $actorId,
            'action' => $action,
            'target_type' => $targetType,
            'target_id' => $targetId,
            'meta' => $meta ?: null,
            'created_at' => now(),
        ]);
    }
}
