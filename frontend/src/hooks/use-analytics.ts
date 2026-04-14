import { useQuery } from "@tanstack/react-query";
import { fetchAnalytics } from "@/lib/api";

export function useAnalytics(
  slug: string,
  period: string = "30d",
  startDate?: string,
  endDate?: string
) {
  return useQuery({
    queryKey: ["analytics", slug, period, startDate, endDate],
    queryFn: () => fetchAnalytics(slug, period, startDate, endDate),
    enabled: !!slug && (period !== "custom" || (!!startDate && !!endDate)),
  });
}
