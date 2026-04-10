import BillingPageClient from "./BillingPageClient";

export function generateStaticParams() {
  return [{ slug: "__placeholder__" }];
}

export const dynamicParams = true;

export default function BillingPage() {
  return <BillingPageClient />;
}
