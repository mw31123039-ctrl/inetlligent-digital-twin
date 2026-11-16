<?php

namespace App\Http\Controllers;

use App\Models\PatientFact;
use App\Services\AuditLog;
use App\Services\ClinicalAiService;
use App\Services\PatientMemory;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

/**
 * Report upload: validate type and size, extract items with page and character location on the private
 * service, and hold anything that could enter the record as `pending_confirmation`. The raw file is not kept.
 */
class ClinicalDocumentController extends Controller
{
    private const RECORDABLE = ['allergy' => 'allergy', 'medication' => 'medication', 'medication_list' => 'medication', 'diagnosis' => 'condition'];

    public function __construct(private ClinicalAiService $ai, private PatientMemory $memory, private AuditLog $audit) {}

    public function store(Request $request): JsonResponse
    {
        $request->validate(['file' => 'required|file|max:5120|mimes:txt,pdf|mimetypes:text/plain,application/pdf']);
        $file = $request->file('file');
        $bytes = file_get_contents($file->getRealPath());
        $isPdf = str_starts_with($bytes, '%PDF-');
        abort_if(! $isPdf && ! mb_check_encoding($bytes, 'UTF-8'), 422, 'Upload a UTF-8 text report or a PDF with a text layer.');
        $result = $this->ai->extractDocument($file->getClientOriginalName(), $isPdf ? 'application/pdf' : 'text/plain', $bytes);
        $userId = $request->user()->id;
        $stored = [];
        if ($this->memory->consent($userId) && $result['unsupported_reason'] === null) {
            foreach ($result['items'] as $item) {
                if (! isset(self::RECORDABLE[$item['kind']]) || ! $item['value']) {
                    continue;
                }
                $stored[] = PatientFact::create([
                    'user_id' => $userId, 'kind' => self::RECORDABLE[$item['kind']], 'status' => 'pending_confirmation', 'provenance' => 'document_extract', 'source_type' => 'document',
                    'source_ref' => substr($result['document_sha256'], 0, 64),
                    'payload' => ['label' => mb_substr($item['value'], 0, 200), 'details' => $item['certainty'], 'anatomy_id' => null, 'recorded_at' => now()->toIso8601String(),
                        'location' => ['page' => $item['location']['page'], 'line' => $item['location']['line'], 'start' => $item['location']['start'], 'end' => $item['location']['end'], 'text' => mb_substr($item['text'], 0, 300)],
                        'document_sha256' => $result['document_sha256']],
                    'expires_at' => now()->addDays(config('ai.pending_extract_days')),
                ])->id;
            }
        }
        $this->audit->record('document.extracted', $userId, $userId, 'document', substr($result['document_sha256'], 0, 16), [
            'items' => count($result['items']), 'pending_saved' => count($stored), 'injection_flags' => count($result['injection_flags']), 'method' => $result['method'],
        ]);

        return response()->json([...$result, 'pending_fact_ids' => $stored, 'stored_for_confirmation' => $stored !== [], 'raw_file_retained' => false]);
    }
}
