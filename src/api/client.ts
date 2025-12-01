/**
 * API client for communicating with the Voice-to-Xero backend.
 */

import * as SecureStore from "expo-secure-store";
import { APIResponse, APIError } from "../types/api";

// API configuration
const API_BASE_URL = __DEV__
  ? "http://localhost:8000"
  : "https://your-production-url.railway.app";

const TOKEN_KEY = "auth_token";

/**
 * Get stored auth token.
 */
export async function getToken(): Promise<string | null> {
  try {
    return await SecureStore.getItemAsync(TOKEN_KEY);
  } catch {
    return null;
  }
}

/**
 * Store auth token securely.
 */
export async function setToken(token: string): Promise<void> {
  await SecureStore.setItemAsync(TOKEN_KEY, token);
}

/**
 * Clear stored auth token.
 */
export async function clearToken(): Promise<void> {
  await SecureStore.deleteItemAsync(TOKEN_KEY);
}

/**
 * API error class for handling structured errors.
 */
export class ApiError extends Error {
  code: string;
  field?: string;
  details?: Record<string, unknown>;

  constructor(error: APIError) {
    super(error.message);
    this.name = "ApiError";
    this.code = error.code;
    this.field = error.field;
    this.details = error.details;
  }
}

/**
 * Make an API request with authentication.
 */
export async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = await getToken();

  const headers: HeadersInit = {
    Accept: "application/json",
    ...options.headers,
  };

  // Add auth header if token exists
  if (token) {
    (headers as Record<string, string>)["Authorization"] = `Bearer ${token}`;
  }

  // Add Content-Type for JSON bodies
  if (options.body && !(options.body instanceof FormData)) {
    (headers as Record<string, string>)["Content-Type"] = "application/json";
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  // Parse response
  const data: APIResponse<T> = await response.json();

  // Handle errors
  if (!data.success || data.error) {
    throw new ApiError(
      data.error || { code: "UNKNOWN_ERROR", message: "Request failed" }
    );
  }

  return data.data as T;
}

/**
 * Upload audio file for voice processing.
 */
export async function uploadAudio(
  endpoint: string,
  audioUri: string,
  additionalFields: Record<string, string> = {}
): Promise<unknown> {
  const token = await getToken();

  const formData = new FormData();

  // Add audio file
  formData.append("audio_file", {
    uri: audioUri,
    type: "audio/m4a",
    name: "recording.m4a",
  } as unknown as Blob);

  // Add additional form fields
  Object.entries(additionalFields).forEach(([key, value]) => {
    formData.append(key, value);
  });

  const headers: HeadersInit = {
    Accept: "application/json",
  };

  if (token) {
    (headers as Record<string, string>)["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    method: "POST",
    headers,
    body: formData,
  });

  const data: APIResponse<unknown> = await response.json();

  if (!data.success || data.error) {
    throw new ApiError(
      data.error || { code: "UPLOAD_ERROR", message: "Audio upload failed" }
    );
  }

  return data.data;
}

// Export base URL for OAuth redirects
export { API_BASE_URL };
