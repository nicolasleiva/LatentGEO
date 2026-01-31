import { useEffect, useState, useRef } from 'react';
import logger from '@/lib/logger';

interface AuditProgress {
  audit_id: number;
  progress: number;
  status: string;
  error_message?: string;
}

export function useAuditWebSocket(auditId: string | number | undefined, onMessage?: (data: AuditProgress) => void) {
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<AuditProgress | null>(null);
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!auditId) return;

    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
    const wsUrl = backendUrl.replace('http', 'ws') + `/ws/progress/${auditId}`;

    logger.log(`Connecting to WebSocket: ${wsUrl}`);
    const socket = new WebSocket(wsUrl);
    socketRef.current = socket;

    socket.onopen = () => {
      logger.log('WebSocket connected');
      setIsConnected(true);
    };

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'ping') return;

        logger.log('WebSocket message received:', data);
        setLastMessage(data);
        if (onMessage) onMessage(data);
      } catch (err) {
        console.error('Failed to parse WebSocket message:', err);
      }
    };

    socket.onclose = () => {
      logger.log('WebSocket disconnected');
      setIsConnected(false);
    };

    socket.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    return () => {
      socket.close();
    };
  }, [auditId, onMessage]);

  return { isConnected, lastMessage };
}
