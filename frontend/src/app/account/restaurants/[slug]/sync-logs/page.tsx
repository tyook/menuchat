import POSSyncLogsPageClient from "./POSSyncLogsPageClient";

export function generateStaticParams() {
  return [{ slug: "__placeholder__" }];
}

export const dynamicParams = true;

export default function POSSyncLogsPage() {
  return <POSSyncLogsPageClient />;
}
