import { useQuery } from "@tanstack/react-query";
import { fetchBillingHistory } from "@/lib/api";

export function useBillingHistory(slug: string) {
  return useQuery({
    queryKey: ["billing-history", slug],
    queryFn: () => fetchBillingHistory(slug),
    enabled: !!slug,
  });
}
