import { useQuery } from "@tanstack/react-query";
import { fetchHallStatus } from "@/lib/api";

export function useHallStatus(slug: string) {
  return useQuery({
    queryKey: ["hall-status", slug],
    queryFn: () => fetchHallStatus(slug),
    enabled: !!slug,
    refetchInterval: 15000,
  });
}
