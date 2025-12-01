/**
 * Authentication API endpoints.
 */

import { apiRequest, setToken, clearToken, API_BASE_URL } from "./client";
import {
  AuthStatusData,
  MobileTokenData,
  OpenAIValidationData,
} from "../types/api";

/**
 * Get current authentication status.
 */
export async function getAuthStatus(): Promise<AuthStatusData> {
  return apiRequest<AuthStatusData>("/auth/mobile/status");
}

/**
 * Exchange web session for mobile JWT token.
 * Call this after completing OAuth in browser.
 */
export async function getMobileToken(): Promise<MobileTokenData> {
  const data = await apiRequest<MobileTokenData>("/auth/mobile/token", {
    method: "POST",
  });

  // Store the token
  await setToken(data.token);

  return data;
}

/**
 * Refresh the mobile JWT token.
 */
export async function refreshToken(): Promise<MobileTokenData> {
  const data = await apiRequest<MobileTokenData>("/auth/mobile/refresh", {
    method: "POST",
  });

  // Update stored token
  await setToken(data.token);

  return data;
}

/**
 * Validate and store OpenAI API key.
 */
export async function validateOpenAI(
  apiKey: string
): Promise<OpenAIValidationData> {
  const formData = new FormData();
  formData.append("api_key", apiKey);

  const data = await apiRequest<OpenAIValidationData>(
    "/auth/mobile/validate-openai",
    {
      method: "POST",
      body: formData,
    }
  );

  // Update token if provided
  if (data.token) {
    await setToken(data.token);
  }

  return data;
}

/**
 * Clear authentication and logout.
 */
export async function logout(): Promise<void> {
  await clearToken();
}

/**
 * Get the Xero OAuth authorization URL.
 * The user should be redirected to this URL in an in-app browser.
 */
export function getXeroAuthUrl(): string {
  return `${API_BASE_URL}/auth/start`;
}
