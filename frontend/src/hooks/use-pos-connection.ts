import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  disconnectPOS,
  fetchPOSConnection,
  initiatePOSConnect,
  updatePOSConnection,
} from "@/lib/api";

export function usePOSConnection(slug: string) {
  return useQuery({
    queryKey: ["pos-connection", slug],
    queryFn: () => fetchPOSConnection(slug),
    enabled: !!slug,
  });
}

export function usePOSConnect() {
  return useMutation({
    mutationFn: ({ slug, posType }: { slug: string; posType: string }) =>
      initiatePOSConnect(slug, posType),
    onSuccess: (data) => {
      window.location.href = data.auth_url;
    },
  });
}

export function usePOSDisconnect(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => disconnectPOS(slug),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pos-connection", slug] });
    },
  });
}

export function usePOSConnectionUpdate(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { payment_mode?: string; external_location_id?: string }) =>
      updatePOSConnection(slug, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pos-connection", slug] });
    },
  });
}
