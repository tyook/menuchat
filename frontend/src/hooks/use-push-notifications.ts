"use client";

import { useEffect, useRef } from "react";
import { isNativePlatform } from "@/lib/native";

export function usePushNotifications() {
  const registered = useRef(false);

  useEffect(() => {
    if (!isNativePlatform() || registered.current) return;

    async function setup() {
      const { PushNotifications } = await import("@capacitor/push-notifications");

      const permission = await PushNotifications.requestPermissions();
      if (permission.receive !== "granted") return;

      await PushNotifications.register();

      PushNotifications.addListener("registration", async (token) => {
        const { getPlatform } = await import("@/lib/native");
        const { apiFetch } = await import("@/lib/api");
        try {
          await apiFetch("/api/devices/register/", {
            method: "POST",
            body: JSON.stringify({
              token: token.value,
              platform: getPlatform(),
            }),
          });
        } catch (e) {
          console.error("Failed to register device token:", e);
        }
      });

      PushNotifications.addListener("pushNotificationReceived", (notification) => {
        console.log("Push received:", notification);
      });

      PushNotifications.addListener("pushNotificationActionPerformed", (action) => {
        const data = action.notification.data;
        if (data?.order_id) {
          console.log("Push action:", data);
        }
      });

      registered.current = true;
    }

    setup();
  }, []);
}
