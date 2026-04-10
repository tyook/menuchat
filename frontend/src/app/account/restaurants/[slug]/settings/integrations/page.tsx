import { Suspense } from "react";
import POSIntegrationsPageClient from "./POSIntegrationsPageClient";

export function generateStaticParams() {
  return [{ slug: "__placeholder__" }];
}

export const dynamicParams = true;

export default function POSIntegrationsPage() {
  return (
    <Suspense>
      <POSIntegrationsPageClient />
    </Suspense>
  );
}
