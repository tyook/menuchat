import { useMutation } from "@tanstack/react-query";
import { createPayment } from "@/lib/api";
import type { ConfirmOrderItem } from "@/types";

interface CreatePaymentParams {
  items: ConfirmOrderItem[];
  rawInput: string;
  tableIdentifier: string;
  language: string;
  customerName?: string;
  customerPhone?: string;
}

export function useCreatePayment(slug: string) {
  return useMutation({
    mutationFn: (params: CreatePaymentParams) =>
      createPayment(
        slug,
        params.items,
        params.rawInput,
        params.tableIdentifier,
        params.language,
        params.customerName,
        params.customerPhone
      ),
  });
}
