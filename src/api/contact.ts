/**
 * Contact workflow API endpoints.
 */

import { apiRequest, uploadAudio } from "./client";
import {
  WorkflowInitData,
  StepProcessData,
  StepConfirmData,
  FieldUpdateData,
} from "../types/api";
import { ContactSummaryData, ContactSubmitData } from "../types/contact";

/**
 * Start a new contact workflow.
 */
export async function startContactWorkflow(): Promise<WorkflowInitData> {
  return apiRequest<WorkflowInitData>("/contact/new");
}

/**
 * Process voice input for a contact workflow step.
 */
export async function processContactStep(
  audioUri: string,
  step: string,
  sessionId: string
): Promise<StepProcessData> {
  return uploadAudio("/contact/step", audioUri, {
    step,
    session_id: sessionId,
  }) as Promise<StepProcessData>;
}

/**
 * Confirm current step and advance to next.
 */
export async function confirmContactStep(
  sessionId: string
): Promise<StepConfirmData> {
  const formData = new FormData();
  formData.append("session_id", sessionId);

  return apiRequest<StepConfirmData>("/contact/continue-step", {
    method: "POST",
    body: formData,
  });
}

/**
 * Navigate to a specific step.
 */
export async function goToContactStep(
  sessionId: string,
  step: string
): Promise<StepConfirmData> {
  const formData = new FormData();
  formData.append("session_id", sessionId);
  formData.append("step", step);

  return apiRequest<StepConfirmData>("/contact/go-to-step", {
    method: "POST",
    body: formData,
  });
}

/**
 * Get contact summary data.
 */
export async function getContactSummary(
  sessionId: string
): Promise<ContactSummaryData> {
  return apiRequest<ContactSummaryData>(
    `/contact/summary?session_id=${sessionId}`
  );
}

/**
 * Update a contact field.
 */
export async function updateContactField(
  sessionId: string,
  field: string,
  value: string
): Promise<FieldUpdateData> {
  const formData = new FormData();
  formData.append("session_id", sessionId);
  formData.append("field", field);
  formData.append("value", value);

  return apiRequest<FieldUpdateData>("/contact/update-field", {
    method: "POST",
    body: formData,
  });
}

/**
 * Submit contact to Xero.
 */
export async function submitContact(
  sessionId: string
): Promise<ContactSubmitData> {
  const formData = new FormData();
  formData.append("session_id", sessionId);

  return apiRequest<ContactSubmitData>("/contact/submit", {
    method: "POST",
    body: formData,
  });
}
