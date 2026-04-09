import { useMutation } from "@tanstack/react-query";
import { createTabOrder } from "@/lib/api";
import { useOrderStore } from "@/stores/order-store";
import type { ConfirmOrderItem } from "@/types";

export function useTabOrder(slug: string) {
  const { setStep, setOrderId, setTabData, setError } = useOrderStore();

  return useMutation({
    mutationFn: (params: {
      items: ConfirmOrderItem[];
      rawInput: string;
      tableIdentifier: string;
      language: string;
      customerName?: string;
      customerPhone?: string;
      allergies?: string[];
    }) =>
      createTabOrder(
        slug,
        params.items,
        params.rawInput,
        params.tableIdentifier,
        params.language,
        params.customerName,
        params.customerPhone,
        params.allergies
      ),
    onSuccess: (data) => {
      setOrderId(data.id);
      setTabData(data.tab);
      setStep("submitted");
    },
    onError: (error: Error) => {
      setError(error.message);
    },
  });
}
