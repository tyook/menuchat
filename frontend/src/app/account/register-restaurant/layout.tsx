import type { Metadata } from "next";

export const metadata: Metadata = { title: "Register Restaurant" };

export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
