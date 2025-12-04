/**
 * Generic workflow state management hook.
 */

import { useState, useCallback } from "react";
import { WorkflowStatus, WorkflowSession, StepResult } from "../types/workflow";
import {
  WorkflowInitData,
  StepProcessData,
  StepConfirmData,
} from "../types/api";

/**
 * Convert snake_case keys to camelCase.
 * Backend returns snake_case (Python), frontend uses camelCase (TypeScript).
 */
function snakeToCamelCase(obj: Record<string, unknown>): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(obj)) {
    const camelKey = key.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase());
    result[camelKey] = value;
  }
  return result;
}

interface WorkflowState<T> {
  session: WorkflowSession<T> | null;
  currentStep: string;
  completedSteps: string[];
  stepPrompt: string;
  transcript: string | null;
  parsedData: Record<string, unknown> | null;
  isLoading: boolean;
  error: string | null;
}

interface UseWorkflowReturn<T> extends WorkflowState<T> {
  initializeWorkflow: (data: WorkflowInitData, initialData: T) => void;
  processStepResult: (data: StepProcessData) => void;
  confirmStepResult: (data: StepConfirmData) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  updateWorkflowData: (updates: Partial<T>) => void;
  resetWorkflow: () => void;
  goToStep: (step: string, prompt: string) => void;
  canGoBack: (steps: string[]) => boolean;
  canGoForward: (steps: string[]) => boolean;
  getAdjacentSteps: (steps: string[]) => { prevStep: string | null; nextStep: string | null };
}

export function useWorkflow<T extends object>(
  initialData: T
): UseWorkflowReturn<T> {
  const [state, setState] = useState<WorkflowState<T>>({
    session: null,
    currentStep: "",
    completedSteps: [],
    stepPrompt: "",
    transcript: null,
    parsedData: null,
    isLoading: false,
    error: null,
  });

  /**
   * Initialize workflow from API response.
   */
  const initializeWorkflow = useCallback(
    (data: WorkflowInitData, workflowData: T) => {
      setState({
        session: {
          sessionId: data.session_id,
          currentStep: data.current_step,
          completedSteps: data.completed_steps,
          workflowData,
          status: WorkflowStatus.IN_PROGRESS,
        },
        currentStep: data.current_step,
        completedSteps: data.completed_steps,
        stepPrompt: data.step_prompt,
        transcript: null,
        parsedData: null,
        isLoading: false,
        error: null,
      });
    },
    []
  );

  /**
   * Process step result from voice input.
   */
  const processStepResult = useCallback((data: StepProcessData) => {
    // Convert snake_case to camelCase for frontend compatibility
    const camelCaseData = snakeToCamelCase(data.parsed_data);

    setState((prev) => ({
      ...prev,
      transcript: data.transcript,
      parsedData: data.parsed_data,
      completedSteps: data.completed_steps,
      isLoading: false,
      error: null,
      session: prev.session
        ? {
            ...prev.session,
            completedSteps: data.completed_steps,
            workflowData: {
              ...prev.session.workflowData,
              ...camelCaseData,
            } as T,
          }
        : null,
    }));
  }, []);

  /**
   * Handle step confirmation and navigation.
   */
  const confirmStepResult = useCallback((data: StepConfirmData) => {
    setState((prev) => ({
      ...prev,
      currentStep: data.current_step,
      completedSteps: data.completed_steps,
      stepPrompt: data.step_prompt,
      transcript: null,
      parsedData: null,
      isLoading: false,
      error: null,
      session: prev.session
        ? {
            ...prev.session,
            currentStep: data.current_step,
            completedSteps: data.completed_steps,
          }
        : null,
    }));
  }, []);

  /**
   * Set loading state.
   */
  const setLoading = useCallback((loading: boolean) => {
    setState((prev) => ({ ...prev, isLoading: loading }));
  }, []);

  /**
   * Set error state.
   */
  const setError = useCallback((error: string | null) => {
    setState((prev) => ({ ...prev, error, isLoading: false }));
  }, []);

  /**
   * Update workflow data directly.
   */
  const updateWorkflowData = useCallback((updates: Partial<T>) => {
    setState((prev) => ({
      ...prev,
      session: prev.session
        ? {
            ...prev.session,
            workflowData: {
              ...prev.session.workflowData,
              ...updates,
            },
          }
        : null,
    }));
  }, []);

  /**
   * Reset workflow to initial state.
   */
  const resetWorkflow = useCallback(() => {
    setState({
      session: null,
      currentStep: "",
      completedSteps: [],
      stepPrompt: "",
      transcript: null,
      parsedData: null,
      isLoading: false,
      error: null,
    });
  }, []);

  /**
   * Navigate to a specific step (for back/forward navigation).
   */
  const goToStep = useCallback((step: string, prompt: string) => {
    setState((prev) => ({
      ...prev,
      currentStep: step,
      stepPrompt: prompt,
      transcript: null,
      parsedData: null,
      isLoading: false,
      error: null,
      session: prev.session
        ? {
            ...prev.session,
            currentStep: step,
          }
        : null,
    }));
  }, []);

  /**
   * Check if can navigate back.
   */
  const canGoBack = useCallback(
    (steps: string[]): boolean => {
      const currentIndex = steps.indexOf(state.currentStep);
      return currentIndex > 0;
    },
    [state.currentStep]
  );

  /**
   * Check if can navigate forward (only if next step was previously completed).
   */
  const canGoForward = useCallback(
    (steps: string[]): boolean => {
      const currentIndex = steps.indexOf(state.currentStep);
      const nextStep = steps[currentIndex + 1];
      return currentIndex < steps.length - 1 && state.completedSteps.includes(nextStep);
    },
    [state.currentStep, state.completedSteps]
  );

  /**
   * Get adjacent steps for navigation.
   */
  const getAdjacentSteps = useCallback(
    (steps: string[]): { prevStep: string | null; nextStep: string | null } => {
      const currentIndex = steps.indexOf(state.currentStep);
      return {
        prevStep: currentIndex > 0 ? steps[currentIndex - 1] : null,
        nextStep: currentIndex < steps.length - 1 ? steps[currentIndex + 1] : null,
      };
    },
    [state.currentStep]
  );

  return {
    ...state,
    initializeWorkflow,
    processStepResult,
    confirmStepResult,
    setLoading,
    setError,
    updateWorkflowData,
    resetWorkflow,
    goToStep,
    canGoBack,
    canGoForward,
    getAdjacentSteps,
  };
}
