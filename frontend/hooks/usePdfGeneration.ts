"use client";

import {
  type PdfJobError,
  type PdfJobState,
  type PdfJobStatus,
  useAuditArtifacts,
} from "@/hooks/useAuditArtifacts";

type UsePdfGenerationOptions = {
  auditId: number | string;
  autoDownload?: boolean;
};

const isActivePdfState = (state: PdfJobState): boolean =>
  state.status === "queued" ||
  state.status === "waiting" ||
  state.status === "running";

export type { PdfJobError, PdfJobState, PdfJobStatus };

export function usePdfGeneration({
  auditId,
  autoDownload = true,
}: UsePdfGenerationOptions) {
  const { state, refresh, generatePdf } = useAuditArtifacts({ auditId });
  const pdfState = state.pdf;
  const isSubmitting = state.pdfSubmitting;
  const isPolling = !isSubmitting && isActivePdfState(pdfState);

  return {
    state: pdfState,
    isSubmitting,
    isPolling,
    isBusy: isSubmitting || isPolling,
    refreshStatus: async (): Promise<PdfJobState> => {
      const nextState = await refresh();
      return nextState.pdf;
    },
    generate: (): Promise<PdfJobState> => generatePdf(autoDownload),
  };
}
