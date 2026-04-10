import OrderPageClient from "./OrderPageClient";

export function generateStaticParams() {
  return [{ slug: "__placeholder__" }];
}

export const dynamicParams = true;

export default function OrderPage() {
  return <OrderPageClient />;
}
