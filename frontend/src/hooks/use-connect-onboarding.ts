import { useMutation, useQuery } from "@tanstack/react-query";
import {
  createOnboardingConnectLink,
  fetchOnboardingConnectStatus,
} from "@/lib/api";

export function useConnectOnboardingLink(slug: string) {
  return useMutation({
    mutationFn: ({
      returnUrl,
      refreshUrl,
    }: {
      returnUrl: string;
      refreshUrl: string;
    }) => createOnboardingConnectLink(slug, returnUrl, refreshUrl),
  });
}

export function useConnectOnboardingStatus(slug: string, enabled: boolean) {
  return useQuery({
    queryKey: ["connect-onboarding-status", slug],
    queryFn: () => fetchOnboardingConnectStatus(slug),
    enabled,
  });
}
