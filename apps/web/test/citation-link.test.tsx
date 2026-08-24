import type { AnswerCitation } from "@localguard/contracts";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AnswerCitationLink, buildCitationHref } from "@/components/evidence/citation-link";

const citation: AnswerCitation = {
  id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
  ordinal: 0,
  quote: "Accounts must be disabled within one hour.",
  document_id: "11111111-1111-4111-8111-111111111111",
  revision_id: "22222222-2222-4222-8222-222222222222",
  anchor_key: "lines:10-12",
  anchor_label: "Lines 10–12",
  start_offset: 0,
  end_offset: 43,
};

describe("citation links", () => {
  it("preserves the immutable revision and exact range, including a zero start offset", () => {
    expect(buildCitationHref(citation)).toBe(
      "/documents/11111111-1111-4111-8111-111111111111?anchor=lines%3A10-12&revision_id=22222222-2222-4222-8222-222222222222&start=0&end=43",
    );
  });

  it("names the stored anchor and links to its durable revision", () => {
    render(<AnswerCitationLink citation={citation} />);
    expect(screen.getByRole("link", { name: "Open Document 11111111, Lines 10–12" })).toHaveAttribute(
      "href",
      "/documents/11111111-1111-4111-8111-111111111111?anchor=lines%3A10-12&revision_id=22222222-2222-4222-8222-222222222222&start=0&end=43",
    );
  });
});
