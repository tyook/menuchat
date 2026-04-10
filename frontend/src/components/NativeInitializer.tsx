"use client";

import { usePushNotifications } from "@/hooks/use-push-notifications";

export function NativeInitializer() {
  usePushNotifications();
  return null;
}
