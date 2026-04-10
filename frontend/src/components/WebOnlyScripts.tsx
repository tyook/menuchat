"use client";

import Script from "next/script";
import { isNativePlatform } from "@/lib/native";

export function WebOnlyScripts() {
  if (isNativePlatform()) return null;

  return (
    <>
      <Script
        src="https://accounts.google.com/gsi/client"
        strategy="lazyOnload"
      />
      <Script
        src="https://appleid.cdn-apple.com/appleauth/static/jsapi/appleid/1/en_US/appleid.auth.js"
        strategy="lazyOnload"
      />
    </>
  );
}
