import { useQuery } from "@tanstack/react-query";
import { fetchTab } from "@/lib/api";

export function useTab(slug: string, tableIdentifier: string, enabled = true) {
  return useQuery({
    queryKey: ["tab", slug, tableIdentifier],
    queryFn: () => fetchTab(slug, tableIdentifier),
    enabled: enabled && !!slug && !!tableIdentifier,
  });
}
