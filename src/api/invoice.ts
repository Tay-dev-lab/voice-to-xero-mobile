/**
 * Invoice workflow API endpoints.
 */

import { apiRequest, uploadAudio } from "./client";
import {
  WorkflowInitData,
  StepProcessData,
  StepConfirmData,
  FieldUpdateData,
} from "../types/api";
import {
  InvoiceSummaryData,
  InvoiceSubmitData,
  LineItemConfirmData,
  XeroContact,
} from "../types/invoice";

/**
 * Start a new invoice workflow.
 */
export async function startInvoiceWorkflow(): Promise<WorkflowInitData> {
  return apiRequest<WorkflowInitData>("/invoice/new");
}

/**
 * Process voice input for an invoice workflow step.
 */
export async function processInvoiceStep(
  audioUri: string,
  step: string,
  sessionId: string
): Promise<StepProcessData> {
  return uploadAudio("/invoice/step", audioUri, {
    step,
    session_id: sessionId,
  }) as Promise<StepProcessData>;
}

/**
 * Confirm current step and advance to next.
 */
export async function confirmInvoiceStep(
  sessionId: string
): Promise<StepConfirmData> {
  const formData = new FormData();
  formData.append("session_id", sessionId);

  return apiRequest<StepConfirmData>("/invoice/confirm-step", {
    method: "POST",
    body: formData,
  });
}

/**
 * Confirm a line item and optionally add more.
 */
export async function confirmLineItem(
  sessionId: string,
  addAnother: boolean = false
): Promise<LineItemConfirmData> {
  const formData = new FormData();
  formData.append("session_id", sessionId);
  formData.append("add_another", addAnother.toString());

  return apiRequest<LineItemConfirmData>("/invoice/confirm-line-item", {
    method: "POST",
    body: formData,
  });
}

/**
 * Navigate to a specific step.
 */
export async function goToInvoiceStep(
  sessionId: string,
  step: string
): Promise<StepConfirmData> {
  const formData = new FormData();
  formData.append("session_id", sessionId);
  formData.append("step", step);

  return apiRequest<StepConfirmData>("/invoice/go-to-step", {
    method: "POST",
    body: formData,
  });
}

/**
 * Get invoice summary data.
 */
export async function getInvoiceSummary(
  sessionId: string
): Promise<InvoiceSummaryData> {
  return apiRequest<InvoiceSummaryData>(
    `/invoice/summary?session_id=${sessionId}`
  );
}

/**
 * Update an invoice field.
 */
export async function updateInvoiceField(
  sessionId: string,
  field: string,
  value: string
): Promise<FieldUpdateData> {
  const formData = new FormData();
  formData.append("session_id", sessionId);
  formData.append("field_name", field);
  formData.append("field_value", value);

  return apiRequest<FieldUpdateData>("/invoice/update-field", {
    method: "POST",
    body: formData,
  });
}

/**
 * Submit invoice to Xero.
 */
export async function submitInvoice(
  sessionId: string
): Promise<InvoiceSubmitData> {
  const formData = new FormData();
  formData.append("session_id", sessionId);

  return apiRequest<InvoiceSubmitData>("/invoice/submit-to-xero", {
    method: "POST",
    body: formData,
  });
}

/**
 * Get list of contacts from Xero for dropdown selection.
 */
export async function getXeroContacts(): Promise<{ contacts: XeroContact[] }> {
  return apiRequest<{ contacts: XeroContact[] }>("/invoice/contacts");
}

/**
 * Response type for clear line item operations.
 */
interface ClearLineItemResponse {
  success: boolean;
  item_count: number;
  line_items: Array<{
    description: string;
    quantity: number;
    unit_price: number;
    vat_rate: string;
  }>;
}

/**
 * Clear a specific line item by index.
 */
export async function clearLineItem(
  sessionId: string,
  itemIndex: number
): Promise<ClearLineItemResponse> {
  const formData = new FormData();
  formData.append("session_id", sessionId);
  formData.append("item_index", itemIndex.toString());

  return apiRequest<ClearLineItemResponse>("/invoice/clear-line-item", {
    method: "POST",
    body: formData,
  });
}

/**
 * Clear all line items.
 */
export async function clearAllLineItems(
  sessionId: string
): Promise<ClearLineItemResponse> {
  const formData = new FormData();
  formData.append("session_id", sessionId);

  return apiRequest<ClearLineItemResponse>("/invoice/clear-all-line-items", {
    method: "POST",
    body: formData,
  });
}
