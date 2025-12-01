/**
 * Contact workflow type definitions.
 */

export interface ContactWorkflowData {
  name?: string;
  isOrganization?: boolean;
  emailAddress?: string;
  addressLine1?: string;
  city?: string;
  postalCode?: string;
  country?: string;
}

export interface ContactNameStepData {
  name: string;
  isOrganization: boolean;
}

export interface ContactEmailStepData {
  emailAddress: string;
}

export interface ContactAddressStepData {
  addressLine1: string;
  city: string;
  postalCode: string;
  country: string;
}

export interface ContactSummaryData {
  name?: string;
  is_organization?: boolean;
  email_address?: string;
  address_line1?: string;
  city?: string;
  postal_code?: string;
  country?: string;
  is_complete: boolean;
  editable_fields: string[];
}

export interface ContactSubmitData {
  contact_id: string;
  xero_contact_id?: string;
  name: string;
  email?: string;
}

// Contact workflow step names
export const ContactSteps = {
  WELCOME: "welcome",
  NAME: "name",
  EMAIL: "email",
  ADDRESS: "address",
  REVIEW: "review",
  FINAL_SUBMIT: "final_submit",
  COMPLETE: "complete",
} as const;

export type ContactStep = (typeof ContactSteps)[keyof typeof ContactSteps];
