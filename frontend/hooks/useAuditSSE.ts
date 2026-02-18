import { useEffect, useState, useRef, useCallback } from "react";
import logger from "@/lib/logger";
import {
  buildAuthenticatedSseUrl,
  fetchWithBackendAuth,
} from "@/lib/backend-auth";

interface AuditProgress {
  audit_id: number;
  progress: number;
  status: string;
  error_message?: string;
  geo_score?: number;
  total_pages?: number;
}

interface UseAuditSSEOptions {
  onMessage?: (data: AuditProgress) => void;
  onComplete?: (data: AuditProgress) => void;
  onError?: (error: Error) => void;
  enabled?: boolean;
}

/**
 * Hook para recibir actualizaciones en tiempo real de auditorías usando Server-Sent Events (SSE).
 * Incluye fallback automático a polling si SSE falla.
 *
 * @param auditId - ID de la auditoría a monitorear
 * @param options - Callbacks opcionales para eventos
 * @returns Estado de conexión y último mensaje recibido
 */
export function useAuditSSE(
  auditId: string | number | undefined,
  options: UseAuditSSEOptions = {},
) {
  // Use a ref to keep track of latest options without triggering re-effects
  const optionsRef = useRef(options);

  // Update ref on every render
  useEffect(() => {
    optionsRef.current = options;
  });

  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<AuditProgress | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [useFallback, setUseFallback] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const intentionallyClosedRef = useRef(false);
  const terminalNotifiedRef = useRef(false);
  const maxReconnectAttempts = 3;
  const enabled = options.enabled ?? true;

  const backendUrl =
    process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

  const cleanup = useCallback((intentional = true) => {
    intentionallyClosedRef.current = intentional;
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }
    setIsConnected(false);
  }, []);

  // Fallback: Polling tradicional
  const startPolling = useCallback(() => {
    if (!auditId || !enabled) return;

    logger.log("[Fallback] Using polling instead of SSE");
    setUseFallback(true);

    const poll = async () => {
      try {
        const res = await fetchWithBackendAuth(
          `${backendUrl}/api/audits/${auditId}/status`,
        );
        if (!res.ok) {
          if (res.status === 401 || res.status === 403) {
            const authError = new Error(
              "Unauthorized polling for audit status",
            );
            setError(authError);
            if (optionsRef.current.onError) {
              optionsRef.current.onError(authError);
            }
            cleanup(true);
          }
          return;
        }

        const data: AuditProgress = await res.json();
        setLastMessage(data);

        if (optionsRef.current.onMessage) {
          optionsRef.current.onMessage(data);
        }

        if (data.status === "completed" || data.status === "failed") {
          if (terminalNotifiedRef.current) {
            cleanup(true);
            return;
          }
          terminalNotifiedRef.current = true;
          if (optionsRef.current.onComplete) {
            optionsRef.current.onComplete(data);
          }
          cleanup(true);
        }
      } catch (err) {
        console.error("[Fallback] Polling error:", err);
      }
    };

    // Poll every 3 seconds
    poll();
    pollingIntervalRef.current = setInterval(poll, 3000);
  }, [auditId, backendUrl, cleanup, enabled]);

  const connect = useCallback(async () => {
    if (!auditId || !enabled) return;

    intentionallyClosedRef.current = false;
    terminalNotifiedRef.current = false;
    cleanup(false);

    const sseUrl = await buildAuthenticatedSseUrl(
      backendUrl,
      `/api/sse/audits/${auditId}/progress`,
    );

    logger.log(`[SSE] Connecting to: ${sseUrl}`);

    try {
      const eventSource = new EventSource(sseUrl);
      eventSourceRef.current = eventSource;

      eventSource.onopen = () => {
        logger.log("[SSE] Connection established");
        setIsConnected(true);
        setError(null);
        setUseFallback(false);
        reconnectAttemptsRef.current = 0;
      };

      eventSource.onmessage = (event) => {
        try {
          const data: AuditProgress = JSON.parse(event.data);
          logger.log("[SSE] Message received:", data);

          setLastMessage(data);

          if (optionsRef.current.onMessage) {
            optionsRef.current.onMessage(data);
          }

          if (data.status === "completed" || data.status === "failed") {
            if (terminalNotifiedRef.current) {
              cleanup(true);
              return;
            }
            terminalNotifiedRef.current = true;
            logger.log(`[SSE] Audit ${data.status}, closing connection`);
            if (optionsRef.current.onComplete) {
              optionsRef.current.onComplete(data);
            }
            cleanup(true);
          }
        } catch (err) {
          console.error("[SSE] Failed to parse message:", err);
        }
      };

      eventSource.onerror = (err) => {
        if (intentionallyClosedRef.current || !enabled) {
          return;
        }
        console.error("[SSE] Connection error:", err);
        setIsConnected(false);

        const errorObj = new Error("SSE connection error");
        setError(errorObj);

        if (optionsRef.current.onError) {
          optionsRef.current.onError(errorObj);
        }

        // Try reconnecting, then fallback to polling
        if (reconnectAttemptsRef.current < maxReconnectAttempts) {
          const delay = Math.min(
            1000 * Math.pow(2, reconnectAttemptsRef.current),
            10000,
          );
          logger.log(
            `[SSE] Reconnecting in ${delay}ms (attempt ${reconnectAttemptsRef.current + 1}/${maxReconnectAttempts})`,
          );

          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectAttemptsRef.current++;
            void connect();
          }, delay);
        } else {
          console.warn(
            "[SSE] Max reconnection attempts reached, falling back to polling",
          );
          cleanup(false);
          startPolling();
        }
      };
    } catch (err) {
      console.error("[SSE] Failed to create EventSource:", err);
      startPolling();
    }
  }, [auditId, backendUrl, cleanup, startPolling, enabled]);

  useEffect(() => {
    if (!auditId || !enabled) {
      cleanup(true);
      return;
    }
    void connect();
    return () => cleanup(true);
  }, [connect, cleanup, auditId, enabled]);

  return {
    isConnected,
    lastMessage,
    error,
    useFallback,
    reconnect: connect,
  };
}
