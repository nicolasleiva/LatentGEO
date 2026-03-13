import { render, screen } from "@testing-library/react";

import AuditCompetitiveBenchmarkSection from "@/app/[locale]/audits/[id]/AuditCompetitiveBenchmarkSection";

describe("AuditCompetitiveBenchmarkSection", () => {
  it("renders N/A for incomplete competitor signals while preserving real zeroes", () => {
    render(
      <AuditCompetitiveBenchmarkSection
        audit={{
          geo_score: 27.9,
          target_audit: {
            schema: { schema_presence: { status: "missing" } },
            structure: {
              semantic_html: { score_percent: 51 },
              h1_check: { status: "pass" },
            },
            eeat: { author_presence: { status: "fail" } },
            content: { conversational_tone: { score: 1.8 } },
          },
        }}
        competitors={[
          {
            domain: "valid-zero.example.com",
            url: "https://valid-zero.example.com",
            geo_score: 0,
            schema_present: false,
            structure_score: 0,
            eeat_score: 0,
            h1_present: false,
            tone_score: 0,
          },
          {
            domain: "incomplete.example.com",
            url: "https://incomplete.example.com",
            geo_score: 0,
            schema_present: null,
            structure_score: null,
            eeat_score: null,
            h1_present: null,
            tone_score: null,
          },
        ]}
        comparisonSites={[
          { name: "Your Site", score: 27.9, color: "#000000" },
          { name: "valid-zero.example.com", score: 0, color: "#999999" },
          { name: "incomplete.example.com", score: 0, color: "#666666" },
        ]}
        visibleCompetitors={[
          {
            domain: "valid-zero.example.com",
            url: "https://valid-zero.example.com",
            geo_score: 0,
            schema_present: false,
            structure_score: 0,
            eeat_score: 0,
            h1_present: false,
            tone_score: 0,
          },
          {
            domain: "incomplete.example.com",
            url: "https://incomplete.example.com",
            geo_score: 0,
            schema_present: null,
            structure_score: null,
            eeat_score: null,
            h1_present: null,
            tone_score: null,
          },
        ]}
        showFullBenchmark
        onToggleFullBenchmark={() => {}}
        initialCompetitorCount={2}
      />,
    );

    expect(screen.getAllByText("N/A").length).toBeGreaterThanOrEqual(3);
    expect(screen.getByText("0.0/10")).toBeInTheDocument();
    expect(screen.queryByText("Gap")).not.toBeInTheDocument();
  });
});
