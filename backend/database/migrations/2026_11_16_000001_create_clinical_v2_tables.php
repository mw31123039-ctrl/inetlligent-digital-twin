<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

/**
 * Clinical assessment v2: drafts, consented assessments, patient memory, audit log and expert review.
 * Health content is only ever stored in Laravel `encrypted:array` payload columns. Plain columns hold
 * identifiers, coarse status values and timestamps needed for authorization, retention and queues.
 */
return new class extends Migration
{
    public function up(): void
    {
        Schema::table('users', function (Blueprint $table) {
            // Assigned only by `php artisan humantwin:reviewer`; never by an API request.
            $table->string('role', 20)->default('patient');
        });

        Schema::create('clinical_sessions', function (Blueprint $table) {
            $table->uuid('id')->primary();
            $table->foreignId('user_id')->constrained()->cascadeOnDelete();
            $table->unsignedInteger('revision')->default(0);
            $table->timestamp('expires_at')->index();
        });

        Schema::create('clinical_assessments', function (Blueprint $table) {
            $table->uuid('id')->primary();
            $table->foreignId('user_id')->constrained()->cascadeOnDelete();
            $table->longText('payload');
            $table->string('consent_version');
            $table->timestamp('consented_at');
            $table->timestamp('review_shared_at')->nullable();
            $table->string('review_consent_version')->nullable();
            $table->timestamps();
            $table->index(['user_id', 'created_at']);
            $table->index('review_shared_at');
        });

        Schema::create('patient_memory_consents', function (Blueprint $table) {
            $table->foreignId('user_id')->primary()->constrained()->cascadeOnDelete();
            $table->string('consent_version');
            $table->timestamp('consented_at');
            $table->unsignedSmallInteger('retention_days')->default(365);
            $table->timestamps();
        });

        Schema::create('patient_facts', function (Blueprint $table) {
            $table->uuid('id')->primary();
            $table->foreignId('user_id')->constrained()->cascadeOnDelete();
            $table->string('kind', 20);
            $table->string('status', 24)->default('active');
            $table->string('provenance', 24);
            $table->string('source_type', 20);
            $table->string('source_ref', 100)->nullable();
            $table->uuid('supersedes_id')->nullable();
            $table->text('payload');
            $table->timestamp('confirmed_at')->nullable();
            $table->timestamp('expires_at')->nullable()->index();
            $table->timestamps();
            $table->index(['user_id', 'status']);
        });

        Schema::create('audit_events', function (Blueprint $table) {
            $table->id();
            $table->foreignId('owner_id')->nullable()->constrained('users')->nullOnDelete();
            $table->foreignId('actor_id')->nullable()->constrained('users')->nullOnDelete();
            $table->string('action', 60);
            $table->string('target_type', 40)->nullable();
            $table->string('target_id', 100)->nullable();
            $table->json('meta')->nullable();
            $table->timestamp('created_at')->useCurrent()->index();
            $table->index(['owner_id', 'created_at']);
        });

        Schema::create('review_items', function (Blueprint $table) {
            $table->uuid('id')->primary();
            $table->foreignId('reviewer_id')->constrained('users')->cascadeOnDelete();
            $table->string('target_type', 30);
            $table->string('target_ref', 120);
            $table->string('knowledge_version', 60);
            $table->string('engine_version', 60);
            $table->uuid('shared_assessment_id')->nullable();
            $table->string('status', 20)->default('pending');
            $table->text('payload');
            $table->foreignId('decided_by')->nullable()->constrained('users')->nullOnDelete();
            $table->timestamp('decided_at')->nullable();
            $table->timestamps();
            $table->index(['status', 'created_at']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('review_items');
        Schema::dropIfExists('audit_events');
        Schema::dropIfExists('patient_facts');
        Schema::dropIfExists('patient_memory_consents');
        Schema::dropIfExists('clinical_assessments');
        Schema::dropIfExists('clinical_sessions');
        Schema::table('users', function (Blueprint $table) {
            $table->dropColumn('role');
        });
    }
};
