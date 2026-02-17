import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchCustomerProfile, updateCustomerProfile } from "@/lib/api";
import type { CustomerProfile } from "@/types";

export function useCustomerProfile() {
  return useQuery({
    queryKey: ["customer-profile"],
    queryFn: fetchCustomerProfile,
  });
}

export function useUpdateCustomerProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<CustomerProfile>) => updateCustomerProfile(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["customer-profile"] });
    },
  });
}
