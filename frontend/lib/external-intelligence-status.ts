type BannerSeverity = "error" | "warning";

type ExternalIntelligencePayload = {
  status?: string | null;
  error_code?: string | null;
  error_message?: string | null;
  warning_code?: string | null;
  warning_message?: string | null;
};

type ExternalIntelligenceBanner =
  | {
      severity: BannerSeverity;
      code: string;
      message: string;
    }
  | null;

function normalizeCode(value: unknown): string {
  return typeof value === "string" ? value.trim().toUpperCase() : "";
}

function normalizeMessage(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function unavailableMessageByCode(code: string): string {
  switch (code) {
    case "AGENT1_LLM_TIMEOUT":
      return "External intelligence timed out with the provider. Automatic competitor discovery could not complete.";
    case "AGENT1_LLM_NETWORK":
      return "External intelligence failed due to provider network issues. Automatic competitor discovery could not complete.";
    case "AGENT1_CORE_QUERY_EMPTY":
      return "External intelligence could not keep business-aligned competitor queries after filtering.";
    case "AGENT1_DISABLED":
      return "External intelligence is disabled for this audit run.";
    default:
      return "External intelligence is currently unavailable. Automatic competitor discovery could not complete.";
  }
}

function warningMessageByCode(code: string): string {
  if (code === "AGENT1_CORE_FILTER_DEGRADED") {
    return "External intelligence completed with degraded competitor-query fallback.";
  }
  return "External intelligence completed with warnings.";
}

export function getExternalIntelligenceBanner(
  payload: ExternalIntelligencePayload | null | undefined,
): ExternalIntelligenceBanner {
  if (!payload || typeof payload !== "object") return null;

  const status = normalizeMessage(payload.status).toLowerCase();
  if (status === "unavailable") {
    const code = normalizeCode(payload.error_code);
    return {
      severity: "error",
      code,
      message: unavailableMessageByCode(code),
    };
  }

  if (status === "ok") {
    const code = normalizeCode(payload.warning_code);
    if (!code) return null;
    const warningMessage = normalizeMessage(payload.warning_message);
    return {
      severity: "warning",
      code,
      message: warningMessage || warningMessageByCode(code),
    };
  }

  return null;
}
