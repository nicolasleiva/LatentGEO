"use client";

import { useMemo, useSyncExternalStore } from "react";

import { API_URL } from "@/lib/api-client";
import { fetchWithBackendAuth } from "@/lib/backend-auth";

export type PdfJobStatus =
  | "idle"
  | "queued"
  | "waiting"
  | "running"
  | "completed"
  | "failed";

export type PdfJobError = {
  code?: string | null;
  message?: string | null;
};

export type PdfJobState = {
  audit_id: number;
  job_id: number | null;
  status: PdfJobStatus;
  download_ready: boolean;
  report_id: number | null;
  warnings: string[];
  error: PdfJobError | null;
  started_at: string | null;
  completed_at: string | null;
  retry_after_seconds: number;
  waiting_on?: string | null;
  dependency_job_id?: number | null;
  message: string | null;
};

export type PageSpeedJobStatus =
  | "idle"
  | "queued"
  | "running"
  | "completed"
  | "failed";

export type PageSpeedJobError = {
  code?: string | null;
  message?: string | null;
};

export type PageSpeedJobState = {
  audit_id: number;
  job_id: number | null;
  status: PageSpeedJobStatus;
  pagespeed_available: boolean;
  warnings: string[];
  error: PageSpeedJobError | null;
  started_at: string | null;
  completed_at: string | null;
  retry_after_seconds: number;
  message: string | null;
};

type AuditArtifactsPayload = {
  audit_id?: number;
  pagespeed_status?: string;
  pagespeed_job_id?: number | string | null;
  pagespeed_available?: boolean;
  pagespeed_warnings?: unknown;
  pagespeed_error?: unknown;
  pagespeed_started_at?: string | null;
  pagespeed_completed_at?: string | null;
  pagespeed_retry_after_seconds?: number | string | null;
  pagespeed_message?: string | null;
  pdf_status?: string;
  pdf_job_id?: number | string | null;
  pdf_available?: boolean;
  pdf_report_id?: number | string | null;
  pdf_waiting_on?: string | null;
  pdf_dependency_job_id?: number | string | null;
  pdf_warnings?: unknown;
  pdf_error?: unknown;
  pdf_started_at?: string | null;
  pdf_completed_at?: string | null;
  pdf_retry_after_seconds?: number | string | null;
  pdf_message?: string | null;
};

type ArtifactTransportMode = "idle" | "sse" | "polling";

type AuditArtifactsStoreState = {
  auditId: number;
  pdf: PdfJobState;
  pagespeed: PageSpeedJobState;
  pdfSubmitting: boolean;
  pagespeedSubmitting: boolean;
  transportMode: ArtifactTransportMode;
  sseConnected: boolean;
  lastError: string | null;
};

type Listener = () => void;

const ACTIVE_PDF_STATUSES = new Set<PdfJobStatus>([
  "queued",
  "waiting",
  "running",
]);
const ACTIVE_PAGESPEED_STATUSES = new Set<PageSpeedJobStatus>([
  "queued",
  "running",
]);
const MIN_ACTIVE_RETRY_SECONDS = 3;
const MAX_POLL_DELAY_MS = 30000;
const ARTIFACT_SSE_BASE_PATH = "/api/sse/audits";
const stores = new Map<number, AuditArtifactsStore>();

const buildIdlePdfState = (auditId: number): PdfJobState => ({
  audit_id: auditId,
  job_id: null,
  status: "idle",
  download_ready: false,
  report_id: null,
  warnings: [],
  error: null,
  started_at: null,
  completed_at: null,
  retry_after_seconds: 0,
  waiting_on: null,
  dependency_job_id: null,
  message: null,
});

const buildIdlePageSpeedState = (auditId: number): PageSpeedJobState => ({
  audit_id: auditId,
  job_id: null,
  status: "idle",
  pagespeed_available: false,
  warnings: [],
  error: null,
  started_at: null,
  completed_at: null,
  retry_after_seconds: 0,
  message: null,
});

const buildInitialStoreState = (auditId: number): AuditArtifactsStoreState => ({
  auditId,
  pdf: buildIdlePdfState(auditId),
  pagespeed: buildIdlePageSpeedState(auditId),
  pdfSubmitting: false,
  pagespeedSubmitting: false,
  transportMode: "idle",
  sseConnected: false,
  lastError: null,
});

const asNullableNumber = (value: unknown): number | null => {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
};

const asNullableString = (value: unknown): string | null =>
  typeof value === "string" && value.trim().length > 0 ? value : null;

const normalizeWarnings = (value: unknown): string[] =>
  Array.isArray(value)
    ? value.filter(
        (warning): warning is string =>
          typeof warning === "string" && warning.trim().length > 0,
      )
    : [];

const normalizeError = (
  value: unknown,
): PdfJobError | PageSpeedJobError | null => {
  if (!value || typeof value !== "object") {
    return null;
  }
  const candidate = value as { code?: unknown; message?: unknown };
  return {
    code: typeof candidate.code === "string" ? candidate.code : null,
    message: typeof candidate.message === "string" ? candidate.message : null,
  };
};

const normalizePdfStatus = (payload: unknown, auditId: number): PdfJobState => {
  if (!payload || typeof payload !== "object") {
    return buildIdlePdfState(auditId);
  }

  const candidate = payload as Partial<PdfJobState>;
  const normalizedStatus: PdfJobStatus =
    candidate.status === "queued" ||
    candidate.status === "waiting" ||
    candidate.status === "running" ||
    candidate.status === "completed" ||
    candidate.status === "failed"
      ? candidate.status
      : "idle";

  return {
    audit_id: Number(candidate.audit_id ?? auditId),
    job_id: asNullableNumber(candidate.job_id),
    status: normalizedStatus,
    download_ready: Boolean(candidate.download_ready),
    report_id: asNullableNumber(candidate.report_id),
    warnings: normalizeWarnings(candidate.warnings),
    error: normalizeError(candidate.error),
    started_at: asNullableString(candidate.started_at),
    completed_at: asNullableString(candidate.completed_at),
    retry_after_seconds: Math.max(
      0,
      Number.isFinite(Number(candidate.retry_after_seconds))
        ? Number(candidate.retry_after_seconds)
        : 0,
    ),
    waiting_on: asNullableString(candidate.waiting_on),
    dependency_job_id: asNullableNumber(candidate.dependency_job_id),
    message: asNullableString(candidate.message),
  };
};

const normalizePageSpeedStatus = (
  payload: unknown,
  auditId: number,
): PageSpeedJobState => {
  if (!payload || typeof payload !== "object") {
    return buildIdlePageSpeedState(auditId);
  }

  const candidate = payload as Partial<PageSpeedJobState>;
  const normalizedStatus: PageSpeedJobStatus =
    candidate.status === "queued" ||
    candidate.status === "running" ||
    candidate.status === "completed" ||
    candidate.status === "failed"
      ? candidate.status
      : "idle";

  return {
    audit_id: Number(candidate.audit_id ?? auditId),
    job_id: asNullableNumber(candidate.job_id),
    status: normalizedStatus,
    pagespeed_available: Boolean(candidate.pagespeed_available),
    warnings: normalizeWarnings(candidate.warnings),
    error: normalizeError(candidate.error),
    started_at: asNullableString(candidate.started_at),
    completed_at: asNullableString(candidate.completed_at),
    retry_after_seconds: Math.max(
      0,
      Number.isFinite(Number(candidate.retry_after_seconds))
        ? Number(candidate.retry_after_seconds)
        : 0,
    ),
    message: asNullableString(candidate.message),
  };
};

const normalizeArtifactPayload = (
  payload: unknown,
  auditId: number,
): Pick<AuditArtifactsStoreState, "pdf" | "pagespeed"> => {
  if (!payload || typeof payload !== "object") {
    return {
      pdf: buildIdlePdfState(auditId),
      pagespeed: buildIdlePageSpeedState(auditId),
    };
  }

  const candidate = payload as AuditArtifactsPayload;

  const pdf = normalizePdfStatus(
    {
      audit_id: candidate.audit_id ?? auditId,
      job_id: candidate.pdf_job_id,
      status: candidate.pdf_status,
      download_ready: candidate.pdf_available,
      report_id: candidate.pdf_report_id,
      warnings: candidate.pdf_warnings,
      error: candidate.pdf_error,
      started_at: candidate.pdf_started_at,
      completed_at: candidate.pdf_completed_at,
      retry_after_seconds: candidate.pdf_retry_after_seconds,
      waiting_on: candidate.pdf_waiting_on,
      dependency_job_id: candidate.pdf_dependency_job_id,
      message: candidate.pdf_message,
    },
    auditId,
  );

  const pagespeed = normalizePageSpeedStatus(
    {
      audit_id: candidate.audit_id ?? auditId,
      job_id: candidate.pagespeed_job_id,
      status: candidate.pagespeed_status,
      pagespeed_available: candidate.pagespeed_available,
      warnings: candidate.pagespeed_warnings,
      error: candidate.pagespeed_error,
      started_at: candidate.pagespeed_started_at,
      completed_at: candidate.pagespeed_completed_at,
      retry_after_seconds: candidate.pagespeed_retry_after_seconds,
      message: candidate.pagespeed_message,
    },
    auditId,
  );

  return { pdf, pagespeed };
};

const extractApiErrorMessage = (payload: unknown, fallback: string): string => {
  if (payload && typeof payload === "object") {
    const detail = (payload as { detail?: unknown }).detail;
    if (typeof detail === "string" && detail.trim()) {
      return detail;
    }
    if (detail && typeof detail === "object") {
      const detailMessage = (detail as { message?: unknown }).message;
      if (typeof detailMessage === "string" && detailMessage.trim()) {
        return detailMessage;
      }
    }
    const message = (payload as { message?: unknown }).message;
    if (typeof message === "string" && message.trim()) {
      return message;
    }
    const error = (payload as { error?: { message?: unknown } | unknown })
      .error;
    if (error && typeof error === "object") {
      const errorMessage = (error as { message?: unknown }).message;
      if (typeof errorMessage === "string" && errorMessage.trim()) {
        return errorMessage;
      }
    }
  }
  return fallback;
};

const isPdfActive = (state: PdfJobState): boolean =>
  ACTIVE_PDF_STATUSES.has(state.status);

const isPageSpeedActive = (state: PageSpeedJobState): boolean =>
  ACTIVE_PAGESPEED_STATUSES.has(state.status);

const fetchArtifactsStatus = async (
  auditId: number,
): Promise<AuditArtifactsPayload> => {
  const response = await fetchWithBackendAuth(
    `${API_URL}/api/v1/audits/${auditId}/artifacts-status`,
  );
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(
      extractApiErrorMessage(
        payload,
        "Failed to fetch artifact generation status.",
      ),
    );
  }
  return payload as AuditArtifactsPayload;
};

class AuditArtifactsStore {
  readonly auditId: number;

  private state: AuditArtifactsStoreState;
  private listeners = new Set<Listener>();
  private eventSource: EventSource | null = null;
  private pollTimer: number | null = null;
  private refreshPromise: Promise<AuditArtifactsStoreState> | null = null;
  private pollFailureCount = 0;
  private stateEpoch = 0;

  constructor(auditId: number) {
    this.auditId = auditId;
    this.state = buildInitialStoreState(auditId);
  }

  subscribe = (listener: Listener): (() => void) => {
    this.listeners.add(listener);
    if (this.listeners.size === 1) {
      void this.start();
    }

    return () => {
      this.listeners.delete(listener);
      if (this.listeners.size === 0) {
        this.destroy();
        stores.delete(this.auditId);
      }
    };
  };

  getSnapshot = (): AuditArtifactsStoreState => this.state;

  private emit() {
    for (const listener of this.listeners) {
      listener();
    }
  }

  private setState(
    updater:
      | AuditArtifactsStoreState
      | ((current: AuditArtifactsStoreState) => AuditArtifactsStoreState),
  ) {
    const nextState =
      typeof updater === "function" ? updater(this.state) : updater;
    this.state = nextState;
    this.stateEpoch += 1;
    this.emit();
  }

  private hasActiveArtifacts(state = this.state): boolean {
    return isPdfActive(state.pdf) || isPageSpeedActive(state.pagespeed);
  }

  private activeRetryDelayMs(state = this.state): number {
    const retrySeconds = Math.max(
      MIN_ACTIVE_RETRY_SECONDS,
      state.pdf.retry_after_seconds,
      state.pagespeed.retry_after_seconds,
    );
    const backoffSeconds = Math.min(
      retrySeconds * Math.max(1, 2 ** this.pollFailureCount),
      MAX_POLL_DELAY_MS / 1000,
    );
    return Math.max(1000, backoffSeconds * 1000);
  }

  private clearPolling() {
    if (this.pollTimer !== null) {
      window.clearTimeout(this.pollTimer);
      this.pollTimer = null;
    }
  }

  destroy() {
    this.clearPolling();
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
    this.pollFailureCount = 0;
  }

  private applyArtifactPayload(payload: AuditArtifactsPayload) {
    const next = normalizeArtifactPayload(payload, this.auditId);
    this.setState((current) => ({
      ...current,
      pdf: next.pdf,
      pagespeed: next.pagespeed,
      lastError: null,
    }));

    if (!this.state.sseConnected && this.hasActiveArtifacts()) {
      this.schedulePolling();
      return;
    }

    if (!this.hasActiveArtifacts()) {
      this.clearPolling();
    }
  }

  private ensureEventSource() {
    if (
      this.eventSource ||
      !Number.isFinite(this.auditId) ||
      this.auditId <= 0 ||
      typeof window === "undefined" ||
      typeof EventSource === "undefined" ||
      this.listeners.size === 0
    ) {
      if (typeof EventSource === "undefined" && this.hasActiveArtifacts()) {
        this.schedulePolling();
      }
      return;
    }

    const source = new EventSource(
      `${ARTIFACT_SSE_BASE_PATH}/${encodeURIComponent(String(this.auditId))}/artifacts`,
    );
    this.eventSource = source;

    source.onopen = () => {
      this.pollFailureCount = 0;
      this.clearPolling();
      this.setState((current) => ({
        ...current,
        transportMode: "sse",
        sseConnected: true,
        lastError: null,
      }));
    };

    source.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data) as AuditArtifactsPayload;
        this.applyArtifactPayload(payload);
      } catch (error) {
        this.setState((current) => ({
          ...current,
          lastError:
            error instanceof Error
              ? error.message
              : "Failed to parse artifact stream event.",
        }));
      }
    };

    source.onerror = () => {
      if (this.eventSource) {
        this.eventSource.close();
        this.eventSource = null;
      }
      this.setState((current) => ({
        ...current,
        transportMode: this.hasActiveArtifacts(current) ? "polling" : "idle",
        sseConnected: false,
        lastError: "Artifact stream disconnected.",
      }));
      if (this.hasActiveArtifacts()) {
        this.schedulePolling();
      }
    };
  }

  private schedulePolling() {
    if (
      this.pollTimer !== null ||
      !Number.isFinite(this.auditId) ||
      this.auditId <= 0 ||
      this.listeners.size === 0 ||
      !this.hasActiveArtifacts()
    ) {
      return;
    }

    const delayMs = this.activeRetryDelayMs();
    this.setState((current) => ({
      ...current,
      transportMode: "polling",
      sseConnected: false,
    }));

    this.pollTimer = window.setTimeout(() => {
      this.pollTimer = null;
      void this.pollOnce();
    }, delayMs);
  }

  private async pollOnce() {
    try {
      await this.refresh();
      this.pollFailureCount = 0;
    } catch (error) {
      this.pollFailureCount += 1;
      this.setState((current) => ({
        ...current,
        transportMode: "polling",
        sseConnected: false,
        lastError:
          error instanceof Error
            ? error.message
            : "Failed to poll artifact status.",
      }));
    }

    if (this.hasActiveArtifacts() && !this.state.sseConnected) {
      this.schedulePolling();
    }
  }

  async refresh(): Promise<AuditArtifactsStoreState> {
    if (!Number.isFinite(this.auditId) || this.auditId <= 0) {
      return this.state;
    }
    if (this.refreshPromise) {
      return this.refreshPromise;
    }

    const refreshPromise = (async () => {
      const requestEpoch = this.stateEpoch;
      const payload = await fetchArtifactsStatus(this.auditId);
      if (requestEpoch !== this.stateEpoch) {
        return this.state;
      }
      this.applyArtifactPayload(payload);
      return this.state;
    })();

    this.refreshPromise = refreshPromise;
    try {
      return await refreshPromise;
    } finally {
      if (this.refreshPromise === refreshPromise) {
        this.refreshPromise = null;
      }
    }
  }

  private async start() {
    if (!Number.isFinite(this.auditId) || this.auditId <= 0) {
      return;
    }
    await this.refresh().catch(() => {
      if (this.hasActiveArtifacts()) {
        this.schedulePolling();
      }
    });
    this.ensureEventSource();
  }

  async generatePdf(autoDownload: boolean): Promise<PdfJobState> {
    if (!Number.isFinite(this.auditId) || this.auditId <= 0) {
      throw new Error("Audit ID is invalid.");
    }
    if (this.state.pdfSubmitting) {
      return this.state.pdf;
    }
    if (isPdfActive(this.state.pdf)) {
      if (!this.state.sseConnected) {
        this.schedulePolling();
      }
      return this.state.pdf;
    }
    void autoDownload;

    this.setState((current) => ({ ...current, pdfSubmitting: true }));
    try {
      const response = await fetchWithBackendAuth(
        `${API_URL}/api/v1/audits/${this.auditId}/generate-pdf`,
        { method: "POST" },
      );
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(
          extractApiErrorMessage(payload, "Failed to generate PDF."),
        );
      }

      const pdf = normalizePdfStatus(payload, this.auditId);
      this.setState((current) => ({
        ...current,
        pdf,
        lastError: null,
      }));

      if (!this.state.sseConnected && isPdfActive(pdf)) {
        this.schedulePolling();
      }

      return pdf;
    } finally {
      this.setState((current) => ({ ...current, pdfSubmitting: false }));
    }
  }

  async generatePageSpeed(): Promise<PageSpeedJobState> {
    if (!Number.isFinite(this.auditId) || this.auditId <= 0) {
      throw new Error("Audit ID is invalid.");
    }
    if (this.state.pagespeedSubmitting) {
      return this.state.pagespeed;
    }
    if (isPageSpeedActive(this.state.pagespeed)) {
      if (!this.state.sseConnected) {
        this.schedulePolling();
      }
      return this.state.pagespeed;
    }

    this.setState((current) => ({ ...current, pagespeedSubmitting: true }));
    try {
      const response = await fetchWithBackendAuth(
        `${API_URL}/api/v1/audits/${this.auditId}/pagespeed`,
        { method: "POST" },
      );
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(
          extractApiErrorMessage(payload, "Failed to generate PageSpeed data."),
        );
      }

      const pagespeed = normalizePageSpeedStatus(payload, this.auditId);
      this.setState((current) => ({
        ...current,
        pagespeed,
        lastError: null,
      }));

      if (!this.state.sseConnected && isPageSpeedActive(pagespeed)) {
        this.schedulePolling();
      }

      return pagespeed;
    } finally {
      this.setState((current) => ({ ...current, pagespeedSubmitting: false }));
    }
  }
}

const getStore = (auditId: number): AuditArtifactsStore => {
  const existing = stores.get(auditId);
  if (existing) {
    return existing;
  }
  const created = new AuditArtifactsStore(auditId);
  stores.set(auditId, created);
  return created;
};

type UseAuditArtifactsOptions = {
  auditId: number | string;
};

export function useAuditArtifacts({ auditId }: UseAuditArtifactsOptions) {
  const numericAuditId = Number(auditId);
  const normalizedAuditId = Number.isFinite(numericAuditId)
    ? numericAuditId
    : 0;
  const store = useMemo(() => getStore(normalizedAuditId), [normalizedAuditId]);
  const snapshot = useSyncExternalStore(
    store.subscribe,
    store.getSnapshot,
    store.getSnapshot,
  );

  return {
    state: snapshot,
    refresh: () => store.refresh(),
    generatePdf: (autoDownload = true) => store.generatePdf(autoDownload),
    generatePageSpeed: () => store.generatePageSpeed(),
  };
}

export function __resetAuditArtifactsStoreForTests() {
  for (const store of stores.values()) {
    store.destroy();
  }
  stores.clear();
}
