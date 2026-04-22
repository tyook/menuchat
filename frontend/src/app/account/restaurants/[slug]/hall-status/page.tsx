import HallStatusPageClient from "./HallStatusPageClient";

export function generateStaticParams() {
  return [{ slug: "__placeholder__" }];
}

export const dynamicParams = true;

export default function HallStatusPage() {
  return <HallStatusPageClient />;
}
