import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import OdooDeliveryPageClient from "@/app/[locale]/audits/[id]/odoo-delivery/OdooDeliveryPageClient";
import { fetchWithBackendAuth } from "@/lib/backend-auth";
import { useRouter } from "next/navigation";

vi.mock("next/navigation", () => ({
  useRouter: vi.fn(),
}));

vi.mock("next/link", () => ({
  __esModule: true,
  default: ({ children, href }: any) => <a href={href}>{children}</a>,
}));

vi.mock("@/components/header", () => ({
  Header: () => <div data-testid="header">Header</div>,
}));

vi.mock("@/lib/api-client", () => ({
  API_URL: "http://localhost:8000",
}));

vi.mock("@/lib/backend-auth", () => ({
  fetchWithBackendAuth: vi.fn(),
}));

describe("OdooDeliveryPageClient", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (useRouter as jest.Mock).mockReturnValue({
      refresh: vi.fn(),
    });
  });

  it("keeps articles and commerce decisions inside the Odoo briefing with editable market prefill", async () => {
    const user = userEvent.setup();

    render(
      <OdooDeliveryPageClient
        auditId="20"
        locale="en"
        initialAudit={{
          id: 20,
          market: "LATAM",
          language: "es",
        }}
        initialPlan={{
          selected_connection: {
            id: "conn-1",
            label: "odoo.example.com / prod-db",
            base_url: "https://odoo.example.com",
            database: "prod-db",
            expected_email: "ops@client.com",
            capabilities: {
              website: true,
              website_blog: true,
              website_sale: true,
            },
          },
          connection_status: {
            selected: true,
            status: "connected",
          },
          implementation_packet: {
            title: "Odoo Delivery Pack",
            summary: "Client-ready pack.",
          },
          delivery_summary: {
            fix_count: 0,
            article_count: 0,
            ecommerce_fix_count: 0,
            missing_required_inputs: 0,
            is_ecommerce: true,
          },
          briefing_profile: {},
          required_inputs: [],
          qa_checklist: [],
          odoo_ready_fixes: [],
          article_deliverables: [],
          ecommerce_fixes: [],
        }}
      />,
    );

    expect(screen.getByText("Guided Odoo Briefing")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Template SEO Rollout/i }));

    const marketInput = screen.getByDisplayValue("LATAM");
    expect(marketInput).toHaveValue("LATAM");
    await user.clear(marketInput);
    await user.type(marketInput, "Mexico");
    await user.click(screen.getByRole("button", { name: /Save answer/i }));

    expect(screen.getByText("Mexico")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Spanish/i }));
    expect(
      screen.getByText(/Include article deliverables/i),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Yes, include them/i }));
    expect(screen.getByText("Article count")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /5 articles/i }));
    expect(
      screen.getByText(/Include ecommerce fixes/i),
    ).toBeInTheDocument();
  });

  it("shows the Odoo connection form first when no connection is selected", () => {
    render(
      <OdooDeliveryPageClient
        auditId="20"
        locale="en"
        initialAudit={{
          id: 20,
          url: "https://client.example.com",
        }}
        initialPlan={{
          connection_status: {
            selected: false,
            status: "not_connected",
            message: "Select an Odoo connection before syncing content.",
          },
          implementation_packet: {
            title: "Odoo Delivery Pack",
            summary: "Client-ready pack.",
          },
          delivery_summary: {
            fix_count: 0,
            article_count: 0,
            ecommerce_fix_count: 0,
            missing_required_inputs: 0,
            is_ecommerce: false,
          },
          required_inputs: [],
          qa_checklist: [],
          odoo_ready_fixes: [],
          article_deliverables: [],
          ecommerce_fixes: [],
        }}
      />,
    );

    expect(screen.getByText("Connection")).toBeInTheDocument();
    expect(screen.getByText(/Select an Odoo connection to continue/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText("https://your-odoo.example.com")).toBeInTheDocument();
  });

  it("reuses a saved Odoo connection and assigns it to the audit", async () => {
    const user = userEvent.setup();
    const refresh = vi.fn();
    const fetchMock = vi.mocked(fetchWithBackendAuth);
    (useRouter as jest.Mock).mockReturnValue({ refresh });

    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/v1/odoo/audits/20/connection")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              audit_id: 20,
              odoo_connection_id: "conn-2",
              plan: {
                selected_connection: {
                  id: "conn-2",
                  label: "global.odoo.example / prod-db / Ops",
                  base_url: "https://global.odoo.example",
                  database: "prod-db",
                  expected_email: "ops@client.com",
                  capabilities: {
                    website: true,
                    website_blog: true,
                    website_sale: true,
                  },
                },
                connection_status: { selected: true, status: "connected" },
                implementation_packet: {
                  title: "Odoo Delivery Pack",
                  summary: "Client-ready pack.",
                },
                delivery_summary: {
                  fix_count: 0,
                  article_count: 0,
                  ecommerce_fix_count: 0,
                  missing_required_inputs: 0,
                  is_ecommerce: true,
                },
                required_inputs: [],
                qa_checklist: [],
                odoo_ready_fixes: [],
                article_deliverables: [],
                ecommerce_fixes: [],
              },
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        );
      }

      if (url.endsWith("/api/v1/audits/20")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({ id: 20, market: "LATAM", language: "en" }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        );
      }

      if (url.endsWith("/api/v1/odoo/delivery-plan/20")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              selected_connection: {
                id: "conn-2",
                label: "global.odoo.example / prod-db / Ops",
                base_url: "https://global.odoo.example",
                database: "prod-db",
                expected_email: "ops@client.com",
                capabilities: {
                  website: true,
                  website_blog: true,
                  website_sale: true,
                },
              },
              connection_status: { selected: true, status: "connected" },
              implementation_packet: {
                title: "Odoo Delivery Pack",
                summary: "Client-ready pack.",
              },
              delivery_summary: {
                fix_count: 0,
                article_count: 0,
                ecommerce_fix_count: 0,
                missing_required_inputs: 0,
                is_ecommerce: true,
              },
              required_inputs: [],
              qa_checklist: [],
              odoo_ready_fixes: [],
              article_deliverables: [],
              ecommerce_fixes: [],
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        );
      }

      if (url.endsWith("/api/v1/odoo/connections")) {
        return Promise.resolve(
          new Response(
            JSON.stringify([
              {
                id: "conn-2",
                label: "global.odoo.example / prod-db / Ops",
                base_url: "https://global.odoo.example",
                database: "prod-db",
                expected_email: "ops@client.com",
                capabilities: {
                  website: true,
                  website_blog: true,
                  website_sale: true,
                },
              },
            ]),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        );
      }

      if (url.endsWith("/api/v1/odoo/sync/20")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              audit_id: 20,
              connection_id: "conn-2",
              summary: {},
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        );
      }

      if (url.endsWith("/api/v1/odoo/drafts/20")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              native_created: [],
              draft: [],
              manual_review: [],
              failed: [],
              summary: {},
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        );
      }

      return Promise.resolve(
        new Response("{}", {
          status: init?.method === "PUT" ? 200 : 404,
          headers: { "Content-Type": "application/json" },
        }),
      );
    });

    render(
      <OdooDeliveryPageClient
        auditId="20"
        locale="en"
        initialAudit={{ id: 20, url: "https://client.example.com", market: "LATAM" }}
        initialConnections={[
          {
            id: "conn-2",
            label: "global.odoo.example / prod-db / Ops",
            base_url: "https://global.odoo.example",
            database: "prod-db",
            expected_email: "ops@client.com",
            capabilities: {
              website: true,
              website_blog: true,
              website_sale: true,
            },
          },
        ]}
        initialPlan={{
          connection_status: {
            selected: false,
            status: "not_connected",
            message: "Select an Odoo connection before syncing content.",
          },
          implementation_packet: {
            title: "Odoo Delivery Pack",
            summary: "Client-ready pack.",
          },
          delivery_summary: {
            fix_count: 0,
            article_count: 0,
            ecommerce_fix_count: 0,
            missing_required_inputs: 0,
            is_ecommerce: true,
          },
          required_inputs: [],
          qa_checklist: [],
          odoo_ready_fixes: [],
          article_deliverables: [],
          ecommerce_fixes: [],
        }}
      />,
    );

    await user.click(screen.getByRole("button", { name: /Use connection/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "http://localhost:8000/api/v1/odoo/audits/20/connection",
        expect.objectContaining({ method: "PUT" }),
      );
    });
    await waitFor(() => {
      expect(screen.getByText(/Odoo connection linked to this audit/i)).toBeInTheDocument();
    });
    expect(refresh).toHaveBeenCalled();
  });
});
