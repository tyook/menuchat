import { Preferences } from "@capacitor/preferences";
import { isNativePlatform } from "./native";

const ACCESS_TOKEN_KEY = "access_token";
const REFRESH_TOKEN_KEY = "refresh_token";

export async function getAccessToken(): Promise<string | null> {
  if (!isNativePlatform()) return null;
  const { value } = await Preferences.get({ key: ACCESS_TOKEN_KEY });
  return value;
}

export async function getRefreshToken(): Promise<string | null> {
  if (!isNativePlatform()) return null;
  const { value } = await Preferences.get({ key: REFRESH_TOKEN_KEY });
  return value;
}

export async function setTokens(accessToken: string, refreshToken: string): Promise<void> {
  if (!isNativePlatform()) return;
  await Preferences.set({ key: ACCESS_TOKEN_KEY, value: accessToken });
  await Preferences.set({ key: REFRESH_TOKEN_KEY, value: refreshToken });
}

export async function clearTokens(): Promise<void> {
  if (!isNativePlatform()) return;
  await Preferences.remove({ key: ACCESS_TOKEN_KEY });
  await Preferences.remove({ key: REFRESH_TOKEN_KEY });
}
