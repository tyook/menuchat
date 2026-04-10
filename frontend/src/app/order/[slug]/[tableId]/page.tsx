import TableOrderPageClient from "./TableOrderPageClient";

export function generateStaticParams() {
  return [{ slug: "__placeholder__", tableId: "__placeholder__" }];
}

export const dynamicParams = true;

export default function TableOrderPage() {
  return <TableOrderPageClient />;
}
