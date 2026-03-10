import { render, screen } from "@testing-library/react";

import AuditDetailCompletedPage from "@/app/[locale]/audits/[id]/AuditDetailCompletedPage";

vi.mock("@/components/header", () => ({
  Header: () => <div data-testid="header">Header</div>,
}));

describe("AuditDetailCompletedPage", () => {
  it("renders persistent pipeline diagnostics when overview includes warnings", () => {
    render(
      <AuditDetailCompletedPage
        locale="en"
        auditId="27"
        overview={{
          id: 27,
          url: "https://www.relume.io",
          domain: "www.relume.io",
          status: "completed",
          progress: 100,
          created_at: "2026-03-09T13:00:00Z",
          completed_at: "2026-03-09T13:10:00Z",
          competitor_count: 4,
          fix_plan_count: 12,
          report_ready: true,
          pagespeed_available: true,
          pdf_available: true,
          diagnostics_summary: [
            {
              source: "pdf",
              stage: "generate-pdf",
              severity: "warning",
              code: "pdf_generation_warning_1",
              message:
                "PageSpeed data could not be refreshed in time for this PDF run.",
            },
          ],
        }}
      />,
    );

    expect(screen.getByTestId("pipeline-diagnostics")).toBeInTheDocument();
    expect(screen.getByText("Pipeline Diagnostics")).toBeInTheDocument();
    expect(
      screen.getByText(
        "PageSpeed data could not be refreshed in time for this PDF run.",
      ),
    ).toBeInTheDocument();
  });
});
