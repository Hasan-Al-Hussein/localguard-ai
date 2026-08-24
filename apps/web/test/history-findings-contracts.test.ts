import {
  EvaluationHistoryDetailSchema,
  EvaluationHistoryEntrySchema,
  EvaluationHistoryListSchema,
  EvaluationOverviewSchema,
  FindingSchema,
} from "@localguard/contracts";
import { describe, expect, it } from "vitest";

const digest = "a".repeat(64);
const runId = "20260823T080500000000Z-ollama-aaaaaaaaaaaa";

function currentHistoryEntry() {
  return {
    schema_version: "1.2.0",
    run_id: runId,
    dataset_version: "1.0.2",
    dataset_sha256: digest,
    requested_provider: "ollama",
    runtime_provider: "ollama",
    completed_case_count: 25,
    case_count: 25,
    safety_passed: true,
    quality_passed: false,
    run_passed: false,
    raw_result_sha256: digest,
    comparability_status: "current",
    comparability_note: "Schema 1.2.0 uses the current evaluation contract.",
    integrity_status: "summary_verified",
    integrity_note: "The stored summary identity was verified.",
  } as const;
}

function evidenceDerivedFinding() {
  return {
    id: "11111111-1111-4111-8111-111111111111",
    workflow_run_id: "22222222-2222-4222-8222-222222222222",
    finding_type: "required_action",
    summary: "The Service Desk must disable the vendor account.",
    normalized_value: "2026-09-01T10:00:00Z",
    responsible_party: "Service Desk",
    due_date: "2026-09-01",
    severity: "high",
    cited_chunk_ids: ["chunk-lg-pol-001-l010"],
    cited_marker_ids: ["LG-POL-001:L010"],
    fields: {
      actor: "Service Desk",
      action: "Disable vendor account",
      deadline: "2026-09-01T10:00:00Z",
    },
    origin: "deterministic_evidence_normalizer",
    normalizer_version: "structured-obligation-binding-v2",
    source_marker_sha256: digest,
    derivation_reason: "evidence_binding_confirmed",
    evidence: [],
    created_at: "2026-08-23T08:00:00Z",
  } as const;
}

describe("frozen evaluation history contracts", () => {
  it("parses list metadata without requiring current-run metric fields", () => {
    const parsed = EvaluationHistoryListSchema.parse({
      items: [currentHistoryEntry()],
      total: 1,
      offset: 0,
      limit: 25,
    });

    expect(parsed.items[0]).toMatchObject({
      run_id: runId,
      integrity_status: "summary_verified",
      comparability_status: "current",
    });
  });

  it("keeps the detail envelope stable and rejects an unvalidated current run", () => {
    const parsed = EvaluationHistoryDetailSchema.parse({
      metadata: { ...currentHistoryEntry(), integrity_status: "run_verified" },
      current_run: null,
      legacy_run_metadata: null,
    });

    expect(parsed.current_run).toBeNull();
    expect(() => EvaluationHistoryDetailSchema.parse({
      metadata: { ...currentHistoryEntry(), integrity_status: "run_verified" },
      current_run: { schema_version: "1.2.0" },
      legacy_run_metadata: null,
    })).toThrow();
  });

  it("accepts explicit unavailable overview metrics for a corrupt latest artifact", () => {
    expect(() => EvaluationOverviewSchema.parse({
      run_id: runId,
      schema_version: null,
      runtime_provider: null,
      completed_case_count: null,
      case_count: null,
      safety_passed: null,
      quality_passed: null,
      run_passed: null,
      integrity_status: "corrupt",
      integrity_note: "The summary is malformed.",
      comparability_status: "unavailable",
      comparability_note: "Metrics cannot be compared.",
    })).not.toThrow();
  });

  it("rejects unknown history metadata fields", () => {
    expect(() => EvaluationHistoryEntrySchema.parse({
      ...currentHistoryEntry(),
      invented_metric: 1,
    })).toThrow();
  });
});

describe("finding provenance contract", () => {
  it("accepts a complete evidence-derived actor/action/deadline binding", () => {
    expect(FindingSchema.parse(evidenceDerivedFinding()).fields).toEqual({
      actor: "Service Desk",
      action: "Disable vendor account",
      deadline: "2026-09-01T10:00:00Z",
    });
  });

  it("rejects incomplete evidence-derived fields or source markers", () => {
    const finding = evidenceDerivedFinding();
    expect(() => FindingSchema.parse({
      ...finding,
      fields: { actor: "Service Desk", action: "Disable vendor account" },
      cited_marker_ids: [],
    })).toThrow(/exact actor, action, and deadline fields/);
  });

  it("rejects application normalizer metadata on provider findings", () => {
    expect(() => FindingSchema.parse({
      ...evidenceDerivedFinding(),
      origin: "model",
    })).toThrow(/cannot assert application normalizer provenance/);
  });
});
