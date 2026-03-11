"use client";

import {
  type PageSpeedJobError,
  type PageSpeedJobState,
  type PageSpeedJobStatus,
  useAuditArtifacts,
} from "@/hooks/useAuditArtifacts";

type UsePageSpeedGenerationOptions = {
  auditId: number | string;
};

const isActivePageSpeedState = (state: PageSpeedJobState): boolean =>
  state.status === "queued" || state.status === "running";

export type { PageSpeedJobError, PageSpeedJobState, PageSpeedJobStatus };

export function usePageSpeedGeneration({
  auditId,
}: UsePageSpeedGenerationOptions) {
  const { state, refresh, generatePageSpeed } = useAuditArtifacts({ auditId });
  const pageSpeedState = state.pagespeed;
  const isSubmitting = state.pagespeedSubmitting;
  const isPolling = !isSubmitting && isActivePageSpeedState(pageSpeedState);

  return {
    state: pageSpeedState,
    isSubmitting,
    isPolling,
    isBusy: isSubmitting || isPolling,
    refreshStatus: async (): Promise<PageSpeedJobState> => {
      const nextState = await refresh();
      return nextState.pagespeed;
    },
    generate: (): Promise<PageSpeedJobState> => generatePageSpeed(),
  };
}
