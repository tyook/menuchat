import OrderDetailPageClient from "./OrderDetailPageClient";

export function generateStaticParams() {
  return [{ orderId: "__placeholder__" }];
}

export const dynamicParams = true;

export default function OrderDetailPage() {
  return <OrderDetailPageClient />;
}
