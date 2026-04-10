import AnalyticsPageClient from "./AnalyticsPageClient";

export function generateStaticParams() {
  return [{ slug: "__placeholder__" }];
}

export const dynamicParams = true;

export default function AnalyticsPage() {
  return <AnalyticsPageClient />;
}
