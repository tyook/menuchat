import { useQuery } from "@tanstack/react-query";
import { fetchCustomerOrders, fetchCustomerOrder } from "@/lib/api";

export function useCustomerOrders() {
  return useQuery({
    queryKey: ["customer-orders"],
    queryFn: fetchCustomerOrders,
  });
}

export function useCustomerOrder(orderId: string) {
  return useQuery({
    queryKey: ["customer-order", orderId],
    queryFn: () => fetchCustomerOrder(orderId),
    enabled: !!orderId,
  });
}
