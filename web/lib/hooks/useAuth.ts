"use client";

import { useState, useEffect, useCallback } from "react";
import { setStoreUserId, clearUserData } from "../health-store";
import { apiRequest } from "../api-client";

export interface User {
  id: string;
  email: string;
  displayName?: string;
  emailVerified: boolean;
  isAdmin?: boolean;
  createdAt?: string;
}

const TOKEN_KEY = "medos_auth_token";

export function useAuth() {
  const [user, setUser] = useState<User | null>(null);
  const [token, setTokenState] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const persistToken = useCallback((t: string | null) => {
    setTokenState(t);
    if (t) {
      localStorage.setItem(TOKEN_KEY, t);
      const secure = window.location.protocol === "https:" ? "; Secure" : "";
      document.cookie = `medos_token=${t}; path=/; max-age=${30 * 86400}; SameSite=Lax${secure}`;
    } else {
      localStorage.removeItem(TOKEN_KEY);
      document.cookie = "medos_token=; path=/; max-age=0";
    }
  }, []);

  // Restore session on mount
  useEffect(() => {
    const t = localStorage.getItem(TOKEN_KEY);
    if (!t) {
      setLoading(false);
      return;
    }

    apiRequest("/api/auth/me", { token: t })
      .then((data) => {
        if (data?.user) {
          persistToken(t);
          setUser(data.user);
          setStoreUserId(data.user.id);
        } else {
          persistToken(null);
        }
      })
      .catch(() => {
        persistToken(null);
      })
      .finally(() => setLoading(false));
  }, [persistToken]);

  const register = useCallback(
    async (email: string, password: string, opts?: { displayName?: string }) => {
      try {
        const data = await apiRequest("/api/auth/register", {
          method: "POST",
          json: { email, password, displayName: opts?.displayName },
        });

        persistToken(data.token);
        setUser(data.user);
        setStoreUserId(data.user.id);
        return { ok: true as const, needsVerification: !data.user.emailVerified };
      } catch (err: any) {
        return { ok: false as const, error: err.message || "Registration failed" };
      }
    },
    [persistToken]
  );

  const login = useCallback(
    async (email: string, password: string) => {
      try {
        const data = await apiRequest("/api/auth/login", {
          method: "POST",
          json: { email, password },
        });

        persistToken(data.token);
        setUser(data.user);
        setStoreUserId(data.user.id);
        return { ok: true as const };
      } catch (err: any) {
        return { ok: false as const, error: err.message || "Login failed" };
      }
    },
    [persistToken]
  );

  const verifyEmail = useCallback(async (code: string) => {
    try {
      const t = localStorage.getItem(TOKEN_KEY);
      await apiRequest("/api/auth/verify-email", {
        method: "POST",
        token: t,
        json: { code },
      });

      setUser((u) => (u ? { ...u, emailVerified: true } : u));
      return { ok: true as const };
    } catch (err: any) {
      return { ok: false as const, error: err.message };
    }
  }, []);

  const resendVerification = useCallback(async () => {
    const t = localStorage.getItem(TOKEN_KEY);
    try {
      await apiRequest("/api/auth/resend-verification", {
        method: "POST",
        token: t,
      });
    } catch {}
  }, []);

  const forgotPassword = useCallback(async (email: string) => {
    try {
      const data = await apiRequest("/api/auth/forgot-password", {
        method: "POST",
        json: { email },
      });
      return { ok: true, message: data.message };
    } catch (err: any) {
      return { ok: false, message: err.message };
    }
  }, []);

  const resetPassword = useCallback(
    async (email: string, code: string, newPassword: string) => {
      try {
        const data = await apiRequest("/api/auth/reset-password", {
          method: "POST",
          json: { email, code, newPassword },
        });

        if (data.token) persistToken(data.token);
        if (data.user) {
          setUser(data.user);
          setStoreUserId(data.user.id);
        }
        return { ok: true as const };
      } catch (err: any) {
        return { ok: false as const, error: err.message };
      }
    },
    [persistToken]
  );

  const logout = useCallback(async () => {
    const t = localStorage.getItem(TOKEN_KEY);
    if (t) {
      apiRequest("/api/auth/logout", { method: "POST", token: t }).catch(() => {});
    }
    clearUserData();
    persistToken(null);
    setUser(null);
  }, [persistToken]);

  return {
    user,
    token,
    isAuthenticated: !!user,
    isGuest: !user,
    loading,
    register,
    login,
    verifyEmail,
    resendVerification,
    forgotPassword,
    resetPassword,
    logout,
  };
}
