import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

export function useWsToken(enabled = true) {
  return useQuery({
    queryKey: ["ws-token"],
    queryFn: () => apiFetch<{ token: string }>("/api/auth/ws-token/").then((d) => d.token),
    enabled,
    staleTime: 10 * 60 * 1000, // 10 minutes
    refetchInterval: 10 * 60 * 1000,
  });
}
