import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "com.menuchat.qrordering",
  appName: "MenuChat",
  webDir: "out",
  server: {
    hostname: "app.localhost",
    androidScheme: "https",
    allowNavigation: ["*"],
  },
  plugins: {
    PushNotifications: {
      presentationOptions: ["badge", "sound", "alert"],
    },
  },
};

export default config;
