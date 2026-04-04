import { useQuery } from "@tanstack/react-query";
import { fetchCartUpsell } from "@/lib/api";
import type { ParsedOrderItem } from "@/types";

export function useCartUpsell(slug: string, parsedItems: ParsedOrderItem[]) {
  const items = parsedItems.map((item) => ({
    menu_item_id: item.menu_item_id,
    variant_id: item.variant.id,
    quantity: item.quantity,
  }));

  return useQuery({
    queryKey: ["cart-upsell", slug, items],
    queryFn: () => fetchCartUpsell(slug, items),
    enabled: items.length > 0,
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
}
