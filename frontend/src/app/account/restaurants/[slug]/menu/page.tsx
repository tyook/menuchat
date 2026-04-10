import MenuManagementPageClient from "./MenuManagementPageClient";

export function generateStaticParams() {
  return [{ slug: "__placeholder__" }];
}

export const dynamicParams = true;

export default function MenuManagementPage() {
  return <MenuManagementPageClient />;
}
