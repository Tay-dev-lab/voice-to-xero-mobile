/**
 * Workflow-related type definitions.
 */

export enum WorkflowStatus {
  NOT_STARTED = "not_started",
  IN_PROGRESS = "in_progress",
  COMPLETED = "completed",
  ERROR = "error",
}

export interface WorkflowStep {
  name: string;
  label: string;
  prompt: string;
  isVoiceStep: boolean;
}

export interface WorkflowConfig {
  name: string;
  steps: WorkflowStep[];
  initialStep: string;
}

export interface WorkflowSession<T = object> {
  sessionId: string;
  currentStep: string;
  completedSteps: string[];
  workflowData: T;
  status: WorkflowStatus;
}

export interface StepResult {
  success: boolean;
  transcript?: string;
  parsedData?: Record<string, unknown>;
  error?: string;
  nextStep?: string;
}
