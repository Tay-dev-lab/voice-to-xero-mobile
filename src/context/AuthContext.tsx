/**
 * Authentication context provider.
 */

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  ReactNode,
} from "react";
import * as WebBrowser from "expo-web-browser";
import { getToken, clearToken } from "../api/client";
import {
  getAuthStatus,
  getMobileToken,
  refreshToken,
  validateOpenAI,
  getXeroAuthUrl,
} from "../api/auth";

// Complete auth session handling
WebBrowser.maybeCompleteAuthSession();

interface AuthState {
  isLoading: boolean;
  isAuthenticated: boolean;
  xeroConnected: boolean;
  openaiValid: boolean;
  error: string | null;
}

interface AuthContextType extends AuthState {
  checkAuthStatus: () => Promise<void>;
  startXeroAuth: () => Promise<void>;
  validateOpenAIKey: (apiKey: string) => Promise<boolean>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [state, setState] = useState<AuthState>({
    isLoading: true,
    isAuthenticated: false,
    xeroConnected: false,
    openaiValid: false,
    error: null,
  });

  /**
   * Check current authentication status.
   */
  const checkAuthStatus = useCallback(async () => {
    setState((prev) => ({ ...prev, isLoading: true, error: null }));

    try {
      const token = await getToken();

      if (!token) {
        setState({
          isLoading: false,
          isAuthenticated: false,
          xeroConnected: false,
          openaiValid: false,
          error: null,
        });
        return;
      }

      const status = await getAuthStatus();

      setState({
        isLoading: false,
        isAuthenticated: true,
        xeroConnected: status.xero_connected,
        openaiValid: status.openai_valid,
        error: null,
      });
    } catch (error) {
      // Token might be expired, try to refresh
      try {
        await refreshToken();
        const status = await getAuthStatus();

        setState({
          isLoading: false,
          isAuthenticated: true,
          xeroConnected: status.xero_connected,
          openaiValid: status.openai_valid,
          error: null,
        });
      } catch {
        // Refresh failed, clear token
        await clearToken();
        setState({
          isLoading: false,
          isAuthenticated: false,
          xeroConnected: false,
          openaiValid: false,
          error: null,
        });
      }
    }
  }, []);

  /**
   * Start Xero OAuth flow in browser.
   */
  const startXeroAuth = useCallback(async () => {
    setState((prev) => ({ ...prev, isLoading: true, error: null }));

    try {
      const authUrl = getXeroAuthUrl();

      // Open in-app browser for OAuth
      const result = await WebBrowser.openAuthSessionAsync(
        authUrl,
        "voice-to-xero://oauth/callback"
      );

      if (result.type === "success") {
        // OAuth completed, get mobile token
        await getMobileToken();
        await checkAuthStatus();
      } else if (result.type === "cancel") {
        setState((prev) => ({
          ...prev,
          isLoading: false,
          error: "Authentication cancelled",
        }));
      }
    } catch (error) {
      setState((prev) => ({
        ...prev,
        isLoading: false,
        error: error instanceof Error ? error.message : "Authentication failed",
      }));
    }
  }, [checkAuthStatus]);

  /**
   * Validate OpenAI API key.
   */
  const validateOpenAIKey = useCallback(
    async (apiKey: string): Promise<boolean> => {
      setState((prev) => ({ ...prev, isLoading: true, error: null }));

      try {
        const result = await validateOpenAI(apiKey);

        if (result.valid) {
          setState((prev) => ({
            ...prev,
            isLoading: false,
            openaiValid: true,
          }));
          return true;
        } else {
          setState((prev) => ({
            ...prev,
            isLoading: false,
            error: result.message,
          }));
          return false;
        }
      } catch (error) {
        setState((prev) => ({
          ...prev,
          isLoading: false,
          error: error instanceof Error ? error.message : "Validation failed",
        }));
        return false;
      }
    },
    []
  );

  /**
   * Logout and clear all auth state.
   */
  const logout = useCallback(async () => {
    await clearToken();
    setState({
      isLoading: false,
      isAuthenticated: false,
      xeroConnected: false,
      openaiValid: false,
      error: null,
    });
  }, []);

  // Check auth status on mount
  useEffect(() => {
    checkAuthStatus();
  }, [checkAuthStatus]);

  const value: AuthContextType = {
    ...state,
    checkAuthStatus,
    startXeroAuth,
    validateOpenAIKey,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/**
 * Hook to access auth context.
 */
export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
