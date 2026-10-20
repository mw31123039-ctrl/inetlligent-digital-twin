<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration {
    public function up(): void
    {
        // No symptoms, body regions, messages, or urgency are stored in draft metadata.
        Schema::create('conversation_sessions', function (Blueprint $table) {
            $table->uuid('id')->primary();
            $table->foreignId('user_id')->constrained()->cascadeOnDelete();
            $table->unsignedInteger('revision')->default(0);
            $table->timestamp('expires_at')->index();
        });
        Schema::create('health_assessments', function (Blueprint $table) {
            $table->uuid('id')->primary();
            $table->foreignId('user_id')->constrained()->cascadeOnDelete();
            $table->longText('payload');
            $table->string('consent_version');
            $table->timestamp('consented_at');
            $table->timestamps();
        });
    }
    public function down(): void
    {
        Schema::dropIfExists('health_assessments');
        Schema::dropIfExists('conversation_sessions');
    }
};
