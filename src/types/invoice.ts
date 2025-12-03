/**
 * Invoice workflow type definitions.
 */

export enum VATRate {
  STANDARD = "standard",
  REDUCED = "reduced",
  ZERO_RATED = "zero_rated",
  EXEMPT = "exempt",
}

export interface LineItem {
  description: string;
  quantity: number;
  unitPrice: number;
  vatRate: VATRate;
  lineTotal?: number;
}

export interface InvoiceWorkflowData {
  contactName?: string;
  contactId?: string;
  isOrganization?: boolean;
  dueDate?: string;
  daysFromNow?: number;
  lineItems: LineItem[];
  currentLineItem?: Partial<LineItem>;
}

export interface InvoiceSummaryData {
  contact_name?: string;
  contact_id?: string;
  due_date?: string;
  line_items: Array<{
    description: string;
    quantity: number;
    unit_price: number;
    vat_rate: string;
    line_total: number;
  }>;
  subtotal: number;
  vat_total: number;
  grand_total: number;
  is_complete: boolean;
  editable_fields: string[];
}

export interface LineItemConfirmData {
  // Fields returned when add_another=false (proceeding to review)
  current_step: string;
  completed_steps: string[];
  workflow_data?: Record<string, unknown>;
  step_prompt?: string;
  // Fields returned when add_another=true (adding more items)
  line_items?: LineItem[];
  item_count?: number;
}

export interface InvoiceSubmitData {
  invoice_id: string;
  xero_invoice_id?: string;
  invoice_number?: string;
  contact_name: string;
  total: number;
  status: string;
  online_invoice_url?: string;
  email_sent?: boolean;
  email_error?: string;
}

export interface XeroContact {
  contact_id: string;
  name: string;
  email?: string;
}

// Invoice workflow step names
export const InvoiceSteps = {
  WELCOME: "welcome",
  CONTACT_NAME: "contact_name",
  DUE_DATE: "due_date",
  LINE_ITEM: "line_item",
  REVIEW: "review",
  FINAL_SUBMIT: "final_submit",
  COMPLETE: "complete",
} as const;

export type InvoiceStep = (typeof InvoiceSteps)[keyof typeof InvoiceSteps];
