"use client";

import {
  createContext,
  useContext,
  useState,
  useEffect,
  type ReactNode,
} from "react";
import { useUser } from "@clerk/nextjs";
import { api } from "@/lib/api";

interface AuthUser {
  user_id: number;
  username: string;
}

interface AuthContextValue {
  user: AuthUser | null;
  isLoading: boolean;
}

const STORAGE_KEY = "ig_clerk_user_map";

const AuthContext = createContext<AuthContextValue | null>(null);

/**
 * Derive a deterministic backend username from the Clerk user ID.
 * e.g. "clerk_user_2xABC123"
 */
function clerkIdToUsername(clerkId: string) {
  return `clerk_${clerkId}`;
}

/**
 * Derive a deterministic password from the Clerk user ID.
 * This is only used for the auto-created backend account —
 * real security is handled by Clerk on the frontend.
 */
function clerkIdToPassword(clerkId: string) {
  return `clk_${clerkId}_pw`;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const { user: clerkUser, isLoaded: clerkLoaded } = useUser();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Wait for Clerk to finish loading
    if (!clerkLoaded) return;

    // If not signed in, clear state
    if (!clerkUser) {
      setUser(null);
      setIsLoading(false);
      return;
    }

    async function bridgeToBackend() {
      try {
        const clerkId = clerkUser!.id;
        const username = clerkIdToUsername(clerkId);
        const password = clerkIdToPassword(clerkId);

        // Check localStorage cache first
        const cached = localStorage.getItem(STORAGE_KEY);
        if (cached) {
          try {
            const map = JSON.parse(cached) as Record<string, AuthUser>;
            if (map[clerkId]?.user_id && map[clerkId]?.username) {
              setUser(map[clerkId]);
              setIsLoading(false);
              return;
            }
          } catch {
            // Invalid cache, continue to create/login
          }
        }

        // Try signup first (for new users), fall back to login (existing users)
        let backendUser: { user_id: number; username: string };
        try {
          const res = await api.signup(username, password);
          backendUser = { user_id: res.user_id, username: res.username };
        } catch {
          // User already exists → login instead
          const res = await api.login(username, password);
          backendUser = { user_id: res.user_id, username: res.username };
        }

        // Cache the mapping
        const map = cached ? JSON.parse(cached) : {};
        map[clerkId] = backendUser;
        localStorage.setItem(STORAGE_KEY, JSON.stringify(map));

        setUser(backendUser);
      } catch (e) {
        console.error("Failed to bridge Clerk user to backend:", e);
      } finally {
        setIsLoading(false);
      }
    }

    bridgeToBackend();
  }, [clerkLoaded, clerkUser?.id]);

  return (
    <AuthContext.Provider value={{ user, isLoading }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}
