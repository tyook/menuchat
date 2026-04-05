import { useQuery } from "@tanstack/react-query";
import { fetchAnalytics } from "@/lib/api";

export function useAnalytics(slug: string, period: string = "30d") {
  return useQuery({
    queryKey: ["analytics", slug, period],
    queryFn: () => fetchAnalytics(slug, period),
    enabled: !!slug,
  });
}
