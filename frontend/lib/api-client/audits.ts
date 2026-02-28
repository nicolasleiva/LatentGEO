import { ensureData, typedApiClient } from "./client";

type AuditListItem = {
  id: number;
  url: string;
  domain?: string;
  status: string;
  created_at: string;
  geo_score?: number;
  total_pages?: number;
};

export async function listAudits(): Promise<AuditListItem[]> {
  const result = await typedApiClient.GET("/api/v1/audits/");
  const data = ensureData(result, "Failed to load audits");
  return Array.isArray(data) ? (data as AuditListItem[]) : [];
}

export async function createAudit(input: { url: string }): Promise<{ id: number }> {
  const result = await typedApiClient.POST("/api/v1/audits/", {
    body: input as never,
  });
  return ensureData(result, "Failed to create audit") as { id: number };
}

export async function deleteAudit(auditId: number): Promise<void> {
  const result = await typedApiClient.DELETE("/api/v1/audits/{audit_id}", {
    params: {
      path: { audit_id: auditId },
    },
  });
  if (result.error) {
    const message =
      typeof result.error === "object" && result.error !== null
        ? JSON.stringify(result.error)
        : String(result.error);
    throw new Error(message || "Failed to delete audit");
  }
}
