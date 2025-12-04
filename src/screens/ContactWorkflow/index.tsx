/**
 * Contact workflow screen.
 */

import React, { useEffect, useCallback, useState } from "react";
import { View, Text, StyleSheet, ScrollView, Alert, Modal, TextInput } from "react-native";
import { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { RootStackParamList } from "../../navigation/AppNavigator";
import { useWorkflow } from "../../hooks/useWorkflow";
import {
  startContactWorkflow,
  processContactStep,
  confirmContactStep,
  goToContactStep,
  submitContact,
  updateContactField,
} from "../../api/contact";
import { ContactWorkflowData, ContactSteps } from "../../types/contact";
import { colors, spacing, typography, borderRadius } from "../../constants/theme";
import { Button, Card, LoadingSpinner } from "../../components/common";
import { VoiceRecorder, StepProgress, StepResult, AccumulatedDataCard, NavigationButtons } from "../../components/workflow";

type ContactWorkflowNavigationProp = NativeStackNavigationProp<
  RootStackParamList,
  "ContactWorkflow"
>;

interface ContactWorkflowScreenProps {
  navigation: ContactWorkflowNavigationProp;
}

// Step configuration
const STEPS = [
  { name: ContactSteps.NAME, label: "Name" },
  { name: ContactSteps.EMAIL, label: "Email" },
  { name: ContactSteps.ADDRESS, label: "Address" },
  { name: ContactSteps.REVIEW, label: "Review" },
];

const STEP_PROMPTS: Record<string, string> = {
  [ContactSteps.WELCOME]: "Let's add a new contact. Tap Continue to begin.",
  [ContactSteps.NAME]: "Please say the contact's name. For example: 'John Smith' or 'ABC Company'",
  [ContactSteps.EMAIL]: "Now say the contact's email address.",
  [ContactSteps.ADDRESS]: "Please say the contact's address including street, city, and postal code.",
  [ContactSteps.REVIEW]: "Review the contact details below. You can edit any field before submitting.",
};

const initialContactData: ContactWorkflowData = {
  name: undefined,
  isOrganization: false,
  emailAddress: undefined,
  addressLine1: undefined,
  city: undefined,
  postalCode: undefined,
  country: "GB",
};

export default function ContactWorkflowScreen({
  navigation,
}: ContactWorkflowScreenProps) {
  const workflow = useWorkflow<ContactWorkflowData>(initialContactData);
  const [submitting, setSubmitting] = useState(false);
  const [editingField, setEditingField] = useState<{ name: string; value: string; label: string } | null>(null);

  // Initialize workflow on mount
  useEffect(() => {
    const initWorkflow = async () => {
      workflow.setLoading(true);
      try {
        const data = await startContactWorkflow();
        workflow.initializeWorkflow(data, initialContactData);
      } catch (error) {
        workflow.setError(
          error instanceof Error ? error.message : "Failed to start workflow"
        );
      }
    };

    initWorkflow();
  }, []);

  // Handle voice recording complete
  const handleRecordingComplete = useCallback(
    async (audioUri: string) => {
      if (!workflow.session) return;

      workflow.setLoading(true);
      try {
        const result = await processContactStep(
          audioUri,
          workflow.currentStep,
          workflow.session.sessionId
        );
        workflow.processStepResult(result);
      } catch (error) {
        workflow.setError(
          error instanceof Error ? error.message : "Failed to process recording"
        );
      }
    },
    [workflow]
  );

  // Handle continue to next step
  const handleContinue = useCallback(async () => {
    if (!workflow.session) return;

    workflow.setLoading(true);
    try {
      const result = await confirmContactStep(workflow.session.sessionId);
      workflow.confirmStepResult(result);
    } catch (error) {
      workflow.setError(
        error instanceof Error ? error.message : "Failed to continue"
      );
    }
  }, [workflow]);

  // Handle step navigation
  const handleStepPress = useCallback(
    async (stepName: string) => {
      if (!workflow.session) return;

      workflow.setLoading(true);
      try {
        const result = await goToContactStep(
          workflow.session.sessionId,
          stepName
        );
        workflow.confirmStepResult(result);
      } catch (error) {
        workflow.setError(
          error instanceof Error ? error.message : "Failed to navigate"
        );
      }
    },
    [workflow]
  );

  // Handle submit to Xero
  const handleSubmit = useCallback(async () => {
    if (!workflow.session) return;

    setSubmitting(true);
    try {
      const result = await submitContact(workflow.session.sessionId);
      Alert.alert(
        "Success!",
        `Contact "${result.name}" has been created in Xero.`,
        [
          {
            text: "OK",
            onPress: () => navigation.goBack(),
          },
        ]
      );
    } catch (error) {
      Alert.alert(
        "Error",
        error instanceof Error ? error.message : "Failed to create contact"
      );
    } finally {
      setSubmitting(false);
    }
  }, [workflow, navigation]);

  // Step names array for navigation
  const stepNames = STEPS.map((s) => s.name) as string[];

  // Handle go back navigation
  const handleGoBack = useCallback(async () => {
    if (!workflow.session) return;

    const currentIndex = stepNames.indexOf(workflow.currentStep as string);
    if (currentIndex <= 0) return;

    const prevStep = stepNames[currentIndex - 1] as string;
    if (!prevStep) return;

    workflow.setLoading(true);
    try {
      const result = await goToContactStep(workflow.session.sessionId, prevStep);
      workflow.confirmStepResult(result);
    } catch (error) {
      workflow.setError(
        error instanceof Error ? error.message : "Failed to navigate back"
      );
    }
  }, [workflow, stepNames]);

  // Handle go forward navigation
  const handleGoForward = useCallback(async () => {
    if (!workflow.session) return;

    const currentIndex = stepNames.indexOf(workflow.currentStep as string);
    const nextStep = stepNames[currentIndex + 1] as string;

    if (!nextStep) return;

    workflow.setLoading(true);
    try {
      const result = await goToContactStep(workflow.session.sessionId, nextStep);
      workflow.confirmStepResult(result);
    } catch (error) {
      workflow.setError(
        error instanceof Error ? error.message : "Failed to navigate forward"
      );
    }
  }, [workflow, stepNames]);

  // Handle editing a field
  const handleEditField = useCallback((fieldName: string, currentValue: string) => {
    const labelMap: Record<string, string> = {
      name: "Name",
      email_address: "Email",
      address_line1: "Address",
      city: "City",
      postal_code: "Postal Code",
    };
    setEditingField({
      name: fieldName,
      value: currentValue,
      label: labelMap[fieldName] || fieldName,
    });
  }, []);

  // Save edited field
  const handleSaveEdit = useCallback(async () => {
    if (!editingField || !workflow.session) return;

    workflow.setLoading(true);
    try {
      await updateContactField(
        workflow.session.sessionId,
        editingField.name,
        editingField.value
      );
      // Update local workflow data
      const fieldToDataMap: Record<string, keyof ContactWorkflowData> = {
        name: "name",
        email_address: "emailAddress",
        address_line1: "addressLine1",
        city: "city",
        postal_code: "postalCode",
      };
      const dataField = fieldToDataMap[editingField.name];
      if (dataField) {
        workflow.updateWorkflowData({ [dataField]: editingField.value } as Partial<ContactWorkflowData>);
      }
      setEditingField(null);
    } catch (error) {
      Alert.alert("Error", "Failed to save changes");
    } finally {
      workflow.setLoading(false);
    }
  }, [editingField, workflow]);

  // Loading state
  if (workflow.isLoading && !workflow.session) {
    return <LoadingSpinner message="Starting workflow..." />;
  }

  // Error state
  if (workflow.error && !workflow.session) {
    return (
      <View style={styles.errorContainer}>
        <Text style={styles.errorText}>{workflow.error}</Text>
        <Button
          title="Try Again"
          onPress={() => navigation.replace("ContactWorkflow")}
        />
      </View>
    );
  }

  const isVoiceStep = [
    ContactSteps.NAME,
    ContactSteps.EMAIL,
    ContactSteps.ADDRESS,
  ].includes(workflow.currentStep as any);

  const isReviewStep = workflow.currentStep === ContactSteps.REVIEW;
  const isWelcomeStep = workflow.currentStep === ContactSteps.WELCOME;

  return (
    <View style={styles.container}>
      {/* Step Progress */}
      <StepProgress
        steps={STEPS}
        currentStep={workflow.currentStep}
        completedSteps={workflow.completedSteps}
        onStepPress={handleStepPress}
      />

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
      >
        {/* Step Prompt */}
        <Card style={styles.promptCard}>
          <Text style={styles.promptText}>
            {STEP_PROMPTS[workflow.currentStep] ||
              workflow.stepPrompt ||
              "Continue with the workflow"}
          </Text>
        </Card>

        {/* Accumulated Data Card - Show all collected data including current step */}
        {workflow.currentStep === ContactSteps.NAME && workflow.session?.workflowData.name && (
          <AccumulatedDataCard
            title="Saved Name"
            data={[
              { label: "Name", value: workflow.session.workflowData.name, fieldName: "name", editable: true },
            ]}
            onEditField={handleEditField}
          />
        )}

        {workflow.currentStep === ContactSteps.EMAIL && workflow.session && (
          <AccumulatedDataCard
            title="Contact Details"
            data={[
              { label: "Name", value: workflow.session.workflowData.name || "", fieldName: "name", editable: true },
              { label: "Email", value: workflow.session.workflowData.emailAddress || "", fieldName: "email_address", editable: true },
            ]}
            onEditField={handleEditField}
          />
        )}

        {workflow.currentStep === ContactSteps.ADDRESS && workflow.session && (
          <AccumulatedDataCard
            title="Contact Details"
            data={[
              { label: "Name", value: workflow.session.workflowData.name || "", fieldName: "name", editable: true },
              { label: "Email", value: workflow.session.workflowData.emailAddress || "", fieldName: "email_address", editable: true },
              { label: "Address", value: workflow.session.workflowData.addressLine1 || "", fieldName: "address_line1", editable: true },
              { label: "City", value: workflow.session.workflowData.city || "", fieldName: "city", editable: true },
              { label: "Postal Code", value: workflow.session.workflowData.postalCode || "", fieldName: "postal_code", editable: true },
            ]}
            onEditField={handleEditField}
          />
        )}

        {/* Welcome Step - Just show continue button */}
        {isWelcomeStep && (
          <Button
            title="Continue"
            onPress={handleContinue}
            loading={workflow.isLoading}
          />
        )}

        {/* Voice Input Step */}
        {isVoiceStep && !workflow.transcript && (
          <VoiceRecorder
            onRecordingComplete={handleRecordingComplete}
            disabled={workflow.isLoading}
          />
        )}

        {/* Step Result */}
        {isVoiceStep && workflow.transcript && workflow.parsedData && (
          <StepResult
            transcript={workflow.transcript}
            parsedData={workflow.parsedData}
            onContinue={handleContinue}
            onReRecord={() => {
              workflow.setError(null);
              workflow.processStepResult({
                step: workflow.currentStep,
                transcript: "",
                parsed_data: {},
                requires_confirmation: false,
                session_id: workflow.session?.sessionId || "",
                completed_steps: workflow.completedSteps,
              });
            }}
            loading={workflow.isLoading}
          />
        )}

        {/* Review Step */}
        {isReviewStep && workflow.session && (
          <View style={styles.reviewSection}>
            <Card style={styles.summaryCard}>
              <Text style={styles.summaryTitle}>Contact Summary</Text>
              <View style={styles.summaryRow}>
                <Text style={styles.summaryLabel}>Name</Text>
                <Text style={styles.summaryValue}>
                  {workflow.session.workflowData.name || "-"}
                </Text>
              </View>
              <View style={styles.summaryRow}>
                <Text style={styles.summaryLabel}>Email</Text>
                <Text style={styles.summaryValue}>
                  {workflow.session.workflowData.emailAddress || "-"}
                </Text>
              </View>
              <View style={styles.summaryRow}>
                <Text style={styles.summaryLabel}>Address</Text>
                <Text style={styles.summaryValue}>
                  {workflow.session.workflowData.addressLine1 || "-"}
                </Text>
              </View>
              <View style={styles.summaryRow}>
                <Text style={styles.summaryLabel}>City</Text>
                <Text style={styles.summaryValue}>
                  {workflow.session.workflowData.city || "-"}
                </Text>
              </View>
              <View style={styles.summaryRow}>
                <Text style={styles.summaryLabel}>Postal Code</Text>
                <Text style={styles.summaryValue}>
                  {workflow.session.workflowData.postalCode || "-"}
                </Text>
              </View>
            </Card>

            <Button
              title="Submit to Xero"
              onPress={handleSubmit}
              loading={submitting}
              variant="success"
            />
          </View>
        )}

        {/* Error message */}
        {workflow.error && (
          <Card style={styles.errorCard}>
            <Text style={styles.errorCardText}>{workflow.error}</Text>
          </Card>
        )}

        {/* Navigation Buttons */}
        {!isWelcomeStep && (
          <NavigationButtons
            currentStepIndex={stepNames.indexOf(workflow.currentStep as string)}
            totalSteps={stepNames.length}
            completedSteps={workflow.completedSteps}
            steps={stepNames}
            onBack={handleGoBack}
            onForward={handleGoForward}
            disabled={workflow.isLoading}
          />
        )}
      </ScrollView>

      {/* Edit Field Modal */}
      <Modal
        visible={!!editingField}
        transparent
        animationType="fade"
        onRequestClose={() => setEditingField(null)}
      >
        <View style={styles.editModalOverlay}>
          <View style={styles.editModalContent}>
            <Text style={styles.editModalTitle}>
              Edit {editingField?.label}
            </Text>
            <TextInput
              style={styles.editInput}
              value={editingField?.value || ""}
              onChangeText={(text) =>
                setEditingField((prev) =>
                  prev ? { ...prev, value: text } : null
                )
              }
              autoFocus
              selectTextOnFocus
            />
            <View style={styles.editModalButtons}>
              <Button
                title="Cancel"
                onPress={() => setEditingField(null)}
                variant="outline"
                style={styles.editModalButton}
              />
              <Button
                title="Save"
                onPress={handleSaveEdit}
                loading={workflow.isLoading}
                style={styles.editModalButton}
              />
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    padding: spacing.base,
    paddingBottom: spacing["3xl"],
  },
  promptCard: {
    marginBottom: spacing.lg,
    backgroundColor: colors.gray50,
  },
  promptText: {
    fontSize: typography.fontSize.base,
    color: colors.text,
    textAlign: "center",
    lineHeight: 24,
  },
  reviewSection: {
    gap: spacing.base,
  },
  summaryCard: {
    marginBottom: spacing.base,
  },
  summaryTitle: {
    fontSize: typography.fontSize.lg,
    fontWeight: typography.fontWeight.semibold,
    color: colors.gray800,
    marginBottom: spacing.base,
  },
  summaryRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.gray100,
  },
  summaryLabel: {
    fontSize: typography.fontSize.sm,
    color: colors.textSecondary,
  },
  summaryValue: {
    fontSize: typography.fontSize.sm,
    color: colors.text,
    fontWeight: typography.fontWeight.medium,
  },
  errorContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: spacing.xl,
  },
  errorText: {
    fontSize: typography.fontSize.base,
    color: colors.error,
    textAlign: "center",
    marginBottom: spacing.base,
  },
  errorCard: {
    backgroundColor: "#FEE2E2",
    marginTop: spacing.base,
  },
  errorCardText: {
    color: colors.error,
    fontSize: typography.fontSize.sm,
  },
  // Edit modal styles
  editModalOverlay: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.5)",
    justifyContent: "center",
    alignItems: "center",
    padding: spacing.lg,
  },
  editModalContent: {
    backgroundColor: colors.white,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    width: "100%",
    maxWidth: 400,
  },
  editModalTitle: {
    fontSize: typography.fontSize.lg,
    fontWeight: typography.fontWeight.semibold,
    color: colors.gray800,
    marginBottom: spacing.base,
    textAlign: "center",
  },
  editInput: {
    borderWidth: 1,
    borderColor: colors.gray300,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    fontSize: typography.fontSize.base,
    color: colors.text,
    marginBottom: spacing.base,
  },
  editModalButtons: {
    flexDirection: "row",
    justifyContent: "flex-end",
    gap: spacing.sm,
  },
  editModalButton: {
    flex: 1,
  },
});
