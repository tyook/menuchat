import { useMutation } from "@tanstack/react-query";
import { parseOrder } from "@/lib/api";
import { useOrderStore } from "@/stores/order-store";

export function useParseOrder(slug: string) {
  const setParsedResult = useOrderStore((s) => s.setParsedResult);
  const setError = useOrderStore((s) => s.setError);

  return useMutation({
    mutationFn: (rawInput: string) => parseOrder(slug, rawInput),
    onSuccess: (result) => {
      setParsedResult(result.items, result.allergies ?? [], result.total_price, result.language);
    },
    onError: (err) => {
      setError(err instanceof Error ? err.message : "Failed to parse order");
    },
  });
}
