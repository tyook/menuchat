import { create } from "zustand";
import type { User } from "@/types";
import { setTokens, clearTokens } from "@/lib/token-storage";
import { isNativePlatform } from "@/lib/native";

interface AuthState {
  isAuthenticated: boolean | null;
  user: User | null;
  login: (email: string, password: string) => Promise<void>;
  register: (data: {
    email: string;
    password: string;
    first_name?: string;
    last_name?: string;
    name?: string;
    phone?: string;
    link_order_id?: string;
  }) => Promise<void>;
  googleLogin: (token: string, linkOrderId?: string) => Promise<void>;
  appleLogin: (token: string, name?: string, linkOrderId?: string) => Promise<void>;
  logout: () => Promise<void>;
  checkAuth: () => Promise<boolean>;
  clearAuth: () => void;
}

// Deduplication: if a checkAuth call is already in-flight, reuse its promise
let pendingCheckAuth: Promise<boolean> | null = null;

export const useAuthStore = create<AuthState>((set) => ({
  isAuthenticated: null,
  user: null,

  login: async (email, password) => {
    const { login } = await import("@/lib/api");
    const data = await login(email, password);
    if (isNativePlatform() && data.access_token && data.refresh_token) {
      await setTokens(data.access_token, data.refresh_token);
    }
    set({ isAuthenticated: true, user: data.user });
  },

  register: async (formData) => {
    const { register } = await import("@/lib/api");
    const data = await register(formData);
    if (isNativePlatform() && data.access_token && data.refresh_token) {
      await setTokens(data.access_token, data.refresh_token);
    }
    set({ isAuthenticated: true, user: data.user });
  },

  googleLogin: async (token, linkOrderId) => {
    const { googleAuth } = await import("@/lib/api");
    const data = await googleAuth(token, linkOrderId);
    if (isNativePlatform() && data.access_token && data.refresh_token) {
      await setTokens(data.access_token, data.refresh_token);
    }
    set({ isAuthenticated: true, user: data.user });
  },

  appleLogin: async (token, name, linkOrderId) => {
    const { appleAuth } = await import("@/lib/api");
    const data = await appleAuth(token, name, linkOrderId);
    if (isNativePlatform() && data.access_token && data.refresh_token) {
      await setTokens(data.access_token, data.refresh_token);
    }
    set({ isAuthenticated: true, user: data.user });
  },

  logout: async () => {
    const { logout } = await import("@/lib/api");
    await logout().catch(() => {});
    if (isNativePlatform()) {
      await clearTokens();
    }
    set({ isAuthenticated: false, user: null });
  },

  checkAuth: async () => {
    if (pendingCheckAuth) {
      return pendingCheckAuth;
    }

    pendingCheckAuth = (async () => {
      try {
        const { fetchMe } = await import("@/lib/api");
        const user = await fetchMe();
        set({ isAuthenticated: true, user });
        return true;
      } catch {
        set({ isAuthenticated: false, user: null });
        return false;
      } finally {
        pendingCheckAuth = null;
      }
    })();

    return pendingCheckAuth;
  },

  clearAuth: () => {
    if (isNativePlatform()) {
      clearTokens();
    }
    set({ isAuthenticated: false, user: null });
  },
}));
