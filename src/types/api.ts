/**
 * API response types matching backend schemas.
 */

// Standard API response envelope
export interface APIResponse<T> {
  success: boolean;
  data: T | null;
  error: APIError | null;
}

export interface APIError {
  code: string;
  message: string;
  field?: string;
  details?: Record<string, unknown>;
}

// Auth responses
export interface AuthStatusData {
  xero_connected: boolean;
  openai_valid: boolean;
  ready_for_operations: boolean;
  tenant_id?: string;
  session_active?: boolean;
}

export interface MobileTokenData {
  token: string;
  expires_in: number;
  token_type: string;
  xero_connected: boolean;
  openai_valid: boolean;
}

export interface OpenAIValidationData {
  valid: boolean;
  message: string;
  token?: string;
}

// Workflow responses
export interface WorkflowInitData {
  session_id: string;
  current_step: string;
  step_prompt: string;
  workflow_steps: string[];
  completed_steps: string[];
  csrf_token?: string;
}

export interface StepProcessData {
  step: string;
  transcript: string;
  parsed_data: Record<string, unknown>;
  requires_confirmation: boolean;
  next_step?: string;
  session_id: string;
  completed_steps: string[];
}

export interface StepConfirmData {
  confirmed_step: string;
  current_step: string;
  step_prompt: string;
  completed_steps: string[];
}

export interface FieldUpdateData {
  field: string;
  value: string;
  updated: boolean;
}

// Error codes (matching backend ErrorCodes)
export const ErrorCodes = {
  // Authentication
  AUTH_REQUIRED: "AUTH_REQUIRED",
  AUTH_EXPIRED: "AUTH_EXPIRED",
  INVALID_TOKEN: "INVALID_TOKEN",
  XERO_NOT_CONNECTED: "XERO_NOT_CONNECTED",
  OPENAI_NOT_VALID: "OPENAI_NOT_VALID",

  // Session
  SESSION_EXPIRED: "SESSION_EXPIRED",
  SESSION_INVALID: "SESSION_INVALID",
  SESSION_NOT_FOUND: "SESSION_NOT_FOUND",

  // Validation
  VALIDATION_ERROR: "VALIDATION_ERROR",
  MISSING_FIELD: "MISSING_FIELD",

  // Workflow
  INVALID_STEP: "INVALID_STEP",
  STEP_INCOMPLETE: "STEP_INCOMPLETE",
  WORKFLOW_ERROR: "WORKFLOW_ERROR",

  // Xero
  XERO_ERROR: "XERO_ERROR",
  XERO_AUTH_FAILED: "XERO_AUTH_FAILED",

  // Voice processing
  TRANSCRIPTION_FAILED: "TRANSCRIPTION_FAILED",
  PARSING_FAILED: "PARSING_FAILED",
  AUDIO_ERROR: "AUDIO_ERROR",
} as const;

export type ErrorCode = (typeof ErrorCodes)[keyof typeof ErrorCodes];
