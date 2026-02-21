import { useQuery } from "@tanstack/react-query";
import { fetchRestaurantOrders } from "@/lib/api";

export function useRestaurantOrders(slug: string) {
  return useQuery({
    queryKey: ["restaurant-orders", slug],
    queryFn: () => fetchRestaurantOrders(slug),
    enabled: !!slug,
  });
}
