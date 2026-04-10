"use client";

import { useEffect } from "react";
import { usePushNotifications } from "@/hooks/use-push-notifications";
import { isNativePlatform } from "@/lib/native";
import { DeepLinkHandler } from "./DeepLinkHandler";

export function NativeInitializer() {
  usePushNotifications();

  useEffect(() => {
    if (!isNativePlatform()) return;

    async function configureStatusBar() {
      const { StatusBar, Style } = await import("@capacitor/status-bar");
      await StatusBar.setStyle({ style: Style.Default });
      await StatusBar.setOverlaysWebView({ overlay: true });
    }

    configureStatusBar();
  }, []);

  return <DeepLinkHandler />;
}
