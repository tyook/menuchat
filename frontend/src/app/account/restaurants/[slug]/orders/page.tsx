import OrderHistoryPageClient from "./OrderHistoryPageClient";

export function generateStaticParams() {
  return [{ slug: "__placeholder__" }];
}

export const dynamicParams = true;

export default function OrderHistoryPage() {
  return <OrderHistoryPageClient />;
}
