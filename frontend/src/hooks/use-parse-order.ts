import { useMutation } from "@tanstack/react-query";
import { parseOrder } from "@/lib/api";
import { useOrderStore } from "@/stores/order-store";
import type { ParseOrderResult } from "@/types";

export function useParseOrder(slug: string) {
  const setParsedResult = useOrderStore((s) => s.setParsedResult);
  const setError = useOrderStore((s) => s.setError);

  return useMutation({
    mutationFn: (rawInput: string) => parseOrder(slug, rawInput),
    onSuccess: (result: ParseOrderResult) => {
      if (result.type === "order") {
        setParsedResult(result.items, result.allergies ?? [], result.total_price, result.language);
      }
      // For "recommendation" type, VoiceChatTab handles it via its own onSuccess
    },
    onError: (err) => {
      setError(err instanceof Error ? err.message : "Failed to parse order");
    },
  });
}
