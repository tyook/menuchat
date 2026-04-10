"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { isNativePlatform } from "@/lib/native";

export function DeepLinkHandler() {
  const router = useRouter();

  useEffect(() => {
    if (!isNativePlatform()) return;

    async function setupDeepLinks() {
      const { App } = await import("@capacitor/app");

      App.addListener("appUrlOpen", (event) => {
        try {
          const url = new URL(event.url);
          const path = url.pathname;
          if (path.startsWith("/order/")) {
            router.push(path);
          }
        } catch {
          console.error("Invalid deep link URL:", event.url);
        }
      });
    }

    setupDeepLinks();
  }, [router]);

  return null;
}
