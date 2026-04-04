import { useMutation, useQueryClient } from "@tanstack/react-query";
import { selectPOSVendor } from "@/lib/api";

export function usePOSVendorSelect(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (posType: string) => selectPOSVendor(slug, posType),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pos-connection", slug] });
    },
  });
}
