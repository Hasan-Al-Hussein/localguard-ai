import { FindingSchema } from "@localguard/contracts";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { FindingCard } from "@/components/findings/finding-card";

describe("FindingCard", () => {
  it("shows the evidence-bound fields and disclosed provenance", async () => {
    const digest = "b".repeat(64);
    const finding = FindingSchema.parse({
      id: "11111111-1111-4111-8111-111111111111",
      workflow_run_id: "22222222-2222-4222-8222-222222222222",
      finding_type: "required_action",
      summary: "A vendor account disable action is required.",
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
    });

    render(<FindingCard finding={finding} />);

    expect(screen.getByText("Service Desk", { exact: true })).toBeVisible();
    expect(screen.getByText("Disable vendor account", { exact: true })).toBeVisible();
    expect(screen.getByText("2026-09-01T10:00:00Z", { exact: true })).toBeVisible();
    await userEvent.click(screen.getByText("Finding provenance", { exact: true }));
    expect(screen.getByText("LG-POL-001:L010", { exact: true })).toBeVisible();
    expect(screen.getByText("structured-obligation-binding-v2", { exact: true })).toBeVisible();
    expect(screen.getByText(digest, { exact: true })).toBeVisible();
  });
});
