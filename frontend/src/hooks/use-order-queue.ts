import { useEffect, useRef, useState } from "react";
import { fetchOrderQueue, type OrderQueueInfo } from "@/lib/api";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:5005";
const RECONNECT_INTERVAL = 3000;
const POLL_INTERVAL = 30000;

interface UseOrderQueueOptions {
  slug: string;
  orderId: string | null;
  enabled?: boolean;
}

export function useOrderQueue({ slug, orderId, enabled = true }: UseOrderQueueOptions) {
  const [queueInfo, setQueueInfo] = useState<OrderQueueInfo | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<NodeJS.Timeout>();
  const pollRef = useRef<NodeJS.Timeout>();
  const queueInfoRef = useRef(queueInfo);
  const mountedRef = useRef(false);

  queueInfoRef.current = queueInfo;

  // Single effect that manages the entire WebSocket lifecycle.
  // Only depends on `enabled`, `orderId`, and `slug` — no callback refs.
  useEffect(() => {
    if (!enabled || !orderId) return;

    mountedRef.current = true;

    function stopPolling() {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = undefined;
      }
    }

    function startPolling() {
      stopPolling();
      pollRef.current = setInterval(async () => {
        if (!mountedRef.current) return;
        try {
          const data = await fetchOrderQueue(slug, orderId!);
          if (mountedRef.current) {
            setQueueInfo(data);
            queueInfoRef.current = data;
          }
        } catch {
          // Silently fail — will retry on next interval
        }
      }, POLL_INTERVAL);
    }

    function connect() {
      if (!mountedRef.current) return;

      const qi = queueInfoRef.current;
      if (qi?.status === "ready" || qi?.status === "completed") return;

      // Close any existing connection before opening a new one
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.onerror = null;
        wsRef.current.onmessage = null;
        wsRef.current.onopen = null;
        wsRef.current.close();
        wsRef.current = null;
      }

      console.log("[WS] connecting to", `${WS_URL}/ws/order/${slug}/${orderId}/`);
      const ws = new WebSocket(`${WS_URL}/ws/order/${slug}/${orderId}/`);

      ws.onopen = () => {
        if (!mountedRef.current) { ws.close(); return; }
        console.log("[WS] connected");
        setIsConnected(true);
        stopPolling();
      };

      ws.onmessage = (event) => {
        if (!mountedRef.current) return;
        try {
          const data = JSON.parse(event.data);
          console.log("[WS] message", data);
          setQueueInfo(data);
          queueInfoRef.current = data;
        } catch {
          // Ignore non-JSON messages
        }
      };

      ws.onclose = (event) => {
        if (!mountedRef.current) return;
        console.log("[WS] closed", { code: event.code, reason: event.reason });
        setIsConnected(false);
        const currentQi = queueInfoRef.current;
        if (currentQi?.status === "ready" || currentQi?.status === "completed") return;
        startPolling();
        reconnectRef.current = setTimeout(connect, RECONNECT_INTERVAL);
      };

      ws.onerror = (event) => { console.log("[WS] error", event); ws.close(); };
      wsRef.current = ws;
    }

    connect();

    return () => {
      mountedRef.current = false;
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      stopPolling();
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.onerror = null;
        wsRef.current.onmessage = null;
        wsRef.current.onopen = null;
        wsRef.current.close();
        wsRef.current = null;
      }
      setIsConnected(false);
    };
  }, [enabled, orderId, slug]);

  // Stop everything when order reaches terminal state
  useEffect(() => {
    const isTerminal = queueInfo?.status === "ready" || queueInfo?.status === "completed";
    if (isTerminal) {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = undefined;
      }
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
        wsRef.current = null;
      }
    }
  }, [queueInfo?.status]);

  return {
    queuePosition: queueInfo?.queue_position ?? null,
    estimatedWait: queueInfo?.estimated_wait_minutes ?? null,
    status: queueInfo?.status ?? null,
    busyness: queueInfo?.busyness ?? null,
    isConnected,
  };
}
