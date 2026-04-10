import SettingsPageClient from "./SettingsPageClient";

export function generateStaticParams() {
  return [{ slug: "__placeholder__" }];
}

export const dynamicParams = true;

export default function SettingsPage() {
  return <SettingsPageClient />;
}
