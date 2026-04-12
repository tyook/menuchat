import { useQuery } from "@tanstack/react-query";
import { fetchOrderStatus } from "@/lib/api";

export function useOrderStatus(slug: string, orderId: string) {
  return useQuery({
    queryKey: ["order-status", slug, orderId],
    queryFn: () => fetchOrderStatus(slug, orderId),
    enabled: !!slug && !!orderId,
  });
}
