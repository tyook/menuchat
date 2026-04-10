import KitchenPageClient from "./KitchenPageClient";

export function generateStaticParams() {
  return [{ slug: "__placeholder__" }];
}

export const dynamicParams = true;

export default function KitchenPage() {
  return <KitchenPageClient />;
}
