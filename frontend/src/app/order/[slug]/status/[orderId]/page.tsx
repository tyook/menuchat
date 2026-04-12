import OrderStatusPageClient from "./OrderStatusPageClient";

export function generateStaticParams() {
  return [{ slug: "__placeholder__", orderId: "__placeholder__" }];
}

export const dynamicParams = true;

export default function OrderStatusPage() {
  return <OrderStatusPageClient />;
}
