/**
 * Invoice workflow screen.
 */

import React, { useEffect, useCallback, useState } from "react";
import { View, Text, StyleSheet, ScrollView, Alert, TouchableOpacity, Linking, Modal, FlatList } from "react-native";
import { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { RootStackParamList } from "../../navigation/AppNavigator";
import { useWorkflow } from "../../hooks/useWorkflow";
import {
  startInvoiceWorkflow,
  processInvoiceStep,
  confirmInvoiceStep,
  confirmLineItem,
  goToInvoiceStep,
  getInvoiceSummary,
  submitInvoice,
  getXeroContacts,
  updateInvoiceField,
} from "../../api/invoice";
import {
  InvoiceWorkflowData,
  InvoiceSteps,
  InvoiceSummaryData,
  LineItem,
  XeroContact,
  InvoiceSubmitData,
} from "../../types/invoice";
import { colors, spacing, typography } from "../../constants/theme";
import { Button, Card, LoadingSpinner } from "../../components/common";
import { VoiceRecorder, StepProgress, StepResult } from "../../components/workflow";

type InvoiceWorkflowNavigationProp = NativeStackNavigationProp<
  RootStackParamList,
  "InvoiceWorkflow"
>;

interface InvoiceWorkflowScreenProps {
  navigation: InvoiceWorkflowNavigationProp;
}

// Step configuration
const STEPS = [
  { name: InvoiceSteps.CONTACT_NAME, label: "Contact" },
  { name: InvoiceSteps.DUE_DATE, label: "Due Date" },
  { name: InvoiceSteps.LINE_ITEM, label: "Items" },
  { name: InvoiceSteps.REVIEW, label: "Review" },
];

const STEP_PROMPTS: Record<string, string> = {
  [InvoiceSteps.WELCOME]: "Let's create a new invoice. Tap Continue to begin.",
  [InvoiceSteps.CONTACT_NAME]: "Who is this invoice for? Say the contact or company name.",
  [InvoiceSteps.DUE_DATE]: "When is payment due? Say something like 'in 30 days' or 'March 15th'.",
  [InvoiceSteps.LINE_ITEM]: "Describe the item or service. Include description, quantity, and price.",
  [InvoiceSteps.REVIEW]: "Review your invoice below. You can edit any field before submitting.",
};

const initialInvoiceData: InvoiceWorkflowData = {
  contactName: undefined,
  contactId: undefined,
  isOrganization: false,
  dueDate: undefined,
  daysFromNow: undefined,
  lineItems: [],
  currentLineItem: undefined,
};

export default function InvoiceWorkflowScreen({
  navigation,
}: InvoiceWorkflowScreenProps) {
  const workflow = useWorkflow<InvoiceWorkflowData>(initialInvoiceData);
  const [submitting, setSubmitting] = useState(false);
  const [summary, setSummary] = useState<InvoiceSummaryData | null>(null);
  const [loadingSummary, setLoadingSummary] = useState(false);
  const [contacts, setContacts] = useState<XeroContact[]>([]);
  const [loadingContacts, setLoadingContacts] = useState(false);
  const [selectedContactId, setSelectedContactId] = useState<string>("");
  const [showContactModal, setShowContactModal] = useState(false);

  // Initialize workflow on mount
  useEffect(() => {
    const initWorkflow = async () => {
      workflow.setLoading(true);
      try {
        const data = await startInvoiceWorkflow();
        workflow.initializeWorkflow(data, initialInvoiceData);
      } catch (error) {
        workflow.setError(
          error instanceof Error ? error.message : "Failed to start workflow"
        );
      }
    };

    initWorkflow();
  }, []);

  // Load summary when we have a session
  const loadSummary = useCallback(async () => {
    if (!workflow.session) return;

    setLoadingSummary(true);
    try {
      const summaryData = await getInvoiceSummary(workflow.session.sessionId);
      setSummary(summaryData);
    } catch {
      // Silent fail for summary - not critical
    } finally {
      setLoadingSummary(false);
    }
  }, [workflow.session]);

  // Reload summary when step changes or workflow updates
  useEffect(() => {
    if (workflow.session && workflow.currentStep !== InvoiceSteps.WELCOME) {
      loadSummary();
    }
  }, [workflow.currentStep, workflow.session, loadSummary]);

  // Fetch contacts from Xero when on contact_name step
  useEffect(() => {
    const fetchContacts = async () => {
      if (workflow.currentStep !== InvoiceSteps.CONTACT_NAME) return;
      if (contacts.length > 0) return; // Already loaded

      setLoadingContacts(true);
      try {
        const data = await getXeroContacts();
        setContacts(data.contacts || []);
      } catch (error) {
        console.log("Failed to fetch contacts:", error);
        // Silent fail - voice input still works
      } finally {
        setLoadingContacts(false);
      }
    };

    fetchContacts();
  }, [workflow.currentStep, contacts.length]);

  // Find matching contact by name (for voice input)
  const findMatchingContact = useCallback(
    (name: string): XeroContact | null => {
      if (!name || contacts.length === 0) return null;
      const normalized = name.toLowerCase().trim();
      return contacts.find(
        (c) =>
          c.name.toLowerCase().includes(normalized) ||
          normalized.includes(c.name.toLowerCase())
      ) || null;
    },
    [contacts]
  );

  // Handle contact selection from dropdown
  const handleContactSelect = useCallback(
    async (contactId: string) => {
      if (!workflow.session || !contactId) return;

      const contact = contacts.find((c) => c.contact_id === contactId);
      if (!contact) return;

      setSelectedContactId(contactId);
      workflow.setLoading(true);

      try {
        // Save contact data to backend session
        await updateInvoiceField(workflow.session.sessionId, "contact_name", contact.name);
        await updateInvoiceField(workflow.session.sessionId, "contact_id", contact.contact_id);

        // Show confirmation in UI
        workflow.processStepResult({
          step: InvoiceSteps.CONTACT_NAME,
          transcript: contact.name,
          parsed_data: {
            contact_name: contact.name,
            contact_id: contact.contact_id,
          },
          requires_confirmation: true,
          session_id: workflow.session.sessionId,
          completed_steps: workflow.completedSteps,
        });
      } catch (error) {
        workflow.setError(
          error instanceof Error ? error.message : "Failed to select contact"
        );
      } finally {
        workflow.setLoading(false);
      }
    },
    [workflow, contacts]
  );

  // Handle voice recording complete
  const handleRecordingComplete = useCallback(
    async (audioUri: string) => {
      if (!workflow.session) return;

      workflow.setLoading(true);
      try {
        const result = await processInvoiceStep(
          audioUri,
          workflow.currentStep,
          workflow.session.sessionId
        );

        // Special handling for contact_name step - match against existing contacts
        if (workflow.currentStep === InvoiceSteps.CONTACT_NAME && result.parsed_data) {
          const contactName = result.parsed_data.contact_name as string;
          if (contactName && contacts.length > 0) {
            const match = findMatchingContact(contactName);
            if (match) {
              // Found a matching contact - save to backend and update UI
              await updateInvoiceField(workflow.session.sessionId, "contact_name", match.name);
              await updateInvoiceField(workflow.session.sessionId, "contact_id", match.contact_id);

              workflow.processStepResult({
                ...result,
                parsed_data: {
                  ...result.parsed_data,
                  contact_id: match.contact_id,
                  contact_name: match.name,
                },
              });
              setSelectedContactId(match.contact_id);
            } else {
              // No match found - show error
              workflow.setLoading(false);
              Alert.alert(
                "Contact Not Found",
                `No contact named "${contactName}" exists in Xero. Please add them using the Contact workflow first, or select from the dropdown.`,
                [{ text: "OK" }]
              );
              return;
            }
          } else {
            workflow.processStepResult(result);
          }
        } else {
          workflow.processStepResult(result);
        }
        // Reload summary after recording
        loadSummary();
      } catch (error) {
        workflow.setError(
          error instanceof Error ? error.message : "Failed to process recording"
        );
      }
    },
    [workflow, loadSummary, contacts, findMatchingContact]
  );

  // Handle continue to next step
  const handleContinue = useCallback(async () => {
    if (!workflow.session) return;

    workflow.setLoading(true);
    try {
      const result = await confirmInvoiceStep(workflow.session.sessionId);
      workflow.confirmStepResult(result);
    } catch (error) {
      workflow.setError(
        error instanceof Error ? error.message : "Failed to continue"
      );
    }
  }, [workflow]);

  // Handle line item confirmation (with option to add more)
  const handleConfirmLineItem = useCallback(
    async (addAnother: boolean) => {
      if (!workflow.session) return;

      workflow.setLoading(true);
      try {
        const result = await confirmLineItem(workflow.session.sessionId, addAnother);
        // Reload summary
        await loadSummary();

        if (!addAnother) {
          // Use the result from confirmLineItem to update workflow state
          // This takes us to the review step
          workflow.confirmStepResult({
            confirmed_step: "line_item",
            current_step: result.current_step,
            step_prompt: result.step_prompt || "Review your invoice below.",
            completed_steps: result.completed_steps,
          });
        } else {
          // Clear transcript to show voice recorder again for next item
          workflow.processStepResult({
            step: workflow.currentStep,
            transcript: "",
            parsed_data: {},
            requires_confirmation: false,
            session_id: workflow.session.sessionId,
            completed_steps: result.completed_steps,
          });
        }
      } catch (error) {
        workflow.setError(
          error instanceof Error ? error.message : "Failed to confirm item"
        );
      }
    },
    [workflow, loadSummary]
  );

  // Handle step navigation
  const handleStepPress = useCallback(
    async (stepName: string) => {
      if (!workflow.session) return;

      workflow.setLoading(true);
      try {
        const result = await goToInvoiceStep(
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
      const result = await submitInvoice(workflow.session.sessionId);

      // Build success message
      let message = `Invoice ${result.invoice_number || result.invoice_id} has been created.`;

      if (result.email_sent) {
        message += `\n\nEmail sent to ${result.contact_name}.`;
      } else if (result.email_error) {
        message += `\n\nEmail not sent: ${result.email_error}`;
      }

      // Build buttons
      const buttons: Array<{
        text: string;
        onPress?: () => void;
        style?: "cancel" | "default" | "destructive";
      }> = [];

      // Add "View Invoice" button if URL is available
      if (result.online_invoice_url) {
        buttons.push({
          text: "View Invoice",
          onPress: () => {
            Linking.openURL(result.online_invoice_url!);
          },
        });
      }

      buttons.push({
        text: "Done",
        onPress: () => navigation.goBack(),
        style: "default",
      });

      Alert.alert("Success!", message, buttons);
    } catch (error) {
      Alert.alert(
        "Error",
        error instanceof Error ? error.message : "Failed to create invoice"
      );
    } finally {
      setSubmitting(false);
    }
  }, [workflow, navigation]);

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
          onPress={() => navigation.replace("InvoiceWorkflow")}
        />
      </View>
    );
  }

  const voiceSteps = [
    InvoiceSteps.CONTACT_NAME,
    InvoiceSteps.DUE_DATE,
    InvoiceSteps.LINE_ITEM,
  ] as const;
  const isVoiceStep = voiceSteps.some((step) => step === workflow.currentStep);

  const isReviewStep = workflow.currentStep === InvoiceSteps.REVIEW;
  const isWelcomeStep = workflow.currentStep === InvoiceSteps.WELCOME;
  const isLineItemStep = workflow.currentStep === InvoiceSteps.LINE_ITEM;
  const isContactNameStep = workflow.currentStep === InvoiceSteps.CONTACT_NAME;

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

        {/* Welcome Step - Just show continue button */}
        {isWelcomeStep && (
          <Button
            title="Continue"
            onPress={handleContinue}
            loading={workflow.isLoading}
          />
        )}

        {/* Contact Selection - Dropdown + Voice */}
        {isContactNameStep && !workflow.transcript && (
          <View style={styles.contactSelectionSection}>
            {loadingContacts ? (
              <Text style={styles.loadingText}>Loading contacts...</Text>
            ) : contacts.length > 0 ? (
              <>
                {/* Dropdown Button */}
                <TouchableOpacity
                  style={styles.dropdownButton}
                  onPress={() => setShowContactModal(true)}
                >
                  <Text style={selectedContactId ? styles.dropdownTextSelected : styles.dropdownText}>
                    {selectedContactId
                      ? contacts.find((c) => c.contact_id === selectedContactId)?.name
                      : "Select a contact..."}
                  </Text>
                  <Text style={styles.dropdownArrow}>▼</Text>
                </TouchableOpacity>

                {/* OR Divider */}
                <Text style={styles.orDivider}>— OR use voice input —</Text>

                {/* Voice Recorder - Always visible */}
                <VoiceRecorder
                  onRecordingComplete={handleRecordingComplete}
                  disabled={workflow.isLoading}
                />

                {/* Contact Selection Modal */}
                <Modal
                  visible={showContactModal}
                  animationType="slide"
                  transparent
                  onRequestClose={() => setShowContactModal(false)}
                >
                  <View style={styles.modalOverlay}>
                    <View style={styles.modalContent}>
                      <Text style={styles.modalTitle}>Select Contact</Text>
                      <FlatList
                        data={contacts}
                        keyExtractor={(item) => item.contact_id}
                        renderItem={({ item }) => (
                          <TouchableOpacity
                            style={styles.contactItem}
                            onPress={() => {
                              handleContactSelect(item.contact_id);
                              setShowContactModal(false);
                            }}
                          >
                            <Text style={styles.contactName}>{item.name}</Text>
                            {item.email && (
                              <Text style={styles.contactEmail}>{item.email}</Text>
                            )}
                          </TouchableOpacity>
                        )}
                        style={styles.contactList}
                      />
                      <Button
                        title="Cancel"
                        onPress={() => setShowContactModal(false)}
                        variant="outline"
                      />
                    </View>
                  </View>
                </Modal>
              </>
            ) : (
              <>
                <Text style={styles.noContactsText}>
                  No contacts found. Use voice input to search or add contacts in the Contact workflow.
                </Text>
                <VoiceRecorder
                  onRecordingComplete={handleRecordingComplete}
                  disabled={workflow.isLoading}
                />
              </>
            )}
          </View>
        )}

        {/* Voice Input Step (for other steps) */}
        {isVoiceStep && !isContactNameStep && !workflow.transcript && (
          <VoiceRecorder
            onRecordingComplete={handleRecordingComplete}
            disabled={workflow.isLoading}
          />
        )}

        {/* Step Result */}
        {isVoiceStep && workflow.transcript && workflow.parsedData && (
          <>
            <StepResult
              transcript={workflow.transcript}
              parsedData={workflow.parsedData}
              onContinue={isLineItemStep ? () => handleConfirmLineItem(false) : handleContinue}
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
            {/* Add Another Line Item button */}
            {isLineItemStep && (
              <Button
                title="Add Another Item"
                onPress={() => handleConfirmLineItem(true)}
                variant="outline"
                disabled={workflow.isLoading}
                style={styles.addAnotherButton}
              />
            )}
          </>
        )}

        {/* Line Items Summary (shown during line item step) */}
        {isLineItemStep && summary && summary.line_items.length > 0 && (
          <Card style={styles.lineItemsCard}>
            <Text style={styles.lineItemsTitle}>
              Items Added ({summary.line_items.length})
            </Text>
            {summary.line_items.map((item, index) => (
              <View key={index} style={styles.lineItemRow}>
                <Text style={styles.lineItemDesc} numberOfLines={1}>
                  {item.description}
                </Text>
                <Text style={styles.lineItemTotal}>
                  £{item.line_total.toFixed(2)}
                </Text>
              </View>
            ))}
          </Card>
        )}

        {/* Review Step */}
        {isReviewStep && workflow.session && summary && (
          <View style={styles.reviewSection}>
            <Card style={styles.summaryCard}>
              <Text style={styles.summaryTitle}>Invoice Summary</Text>

              <View style={styles.summaryRow}>
                <Text style={styles.summaryLabel}>Contact</Text>
                <Text style={styles.summaryValue}>
                  {summary.contact_name || "-"}
                </Text>
              </View>

              <View style={styles.summaryRow}>
                <Text style={styles.summaryLabel}>Due Date</Text>
                <Text style={styles.summaryValue}>
                  {summary.due_date || "-"}
                </Text>
              </View>

              {/* Line Items */}
              <View style={styles.lineItemsSection}>
                <Text style={styles.lineItemsSectionTitle}>Line Items</Text>
                {summary.line_items.map((item, index) => (
                  <View key={index} style={styles.reviewLineItem}>
                    <View style={styles.reviewLineItemHeader}>
                      <Text style={styles.reviewLineItemDesc}>
                        {item.description}
                      </Text>
                    </View>
                    <View style={styles.reviewLineItemDetails}>
                      <Text style={styles.reviewLineItemDetail}>
                        {item.quantity} x £{item.unit_price.toFixed(2)}
                      </Text>
                      <Text style={styles.reviewLineItemTotal}>
                        £{item.line_total.toFixed(2)}
                      </Text>
                    </View>
                  </View>
                ))}
              </View>

              {/* Totals */}
              <View style={styles.totalsSection}>
                <View style={styles.totalRow}>
                  <Text style={styles.totalLabel}>Subtotal</Text>
                  <Text style={styles.totalValue}>
                    £{summary.subtotal.toFixed(2)}
                  </Text>
                </View>
                <View style={styles.totalRow}>
                  <Text style={styles.totalLabel}>VAT</Text>
                  <Text style={styles.totalValue}>
                    £{summary.vat_total.toFixed(2)}
                  </Text>
                </View>
                <View style={[styles.totalRow, styles.grandTotalRow]}>
                  <Text style={styles.grandTotalLabel}>Total</Text>
                  <Text style={styles.grandTotalValue}>
                    £{summary.grand_total.toFixed(2)}
                  </Text>
                </View>
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
      </ScrollView>
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
  addAnotherButton: {
    marginTop: spacing.sm,
  },
  lineItemsCard: {
    marginTop: spacing.base,
  },
  lineItemsTitle: {
    fontSize: typography.fontSize.sm,
    fontWeight: typography.fontWeight.semibold,
    color: colors.gray700,
    marginBottom: spacing.sm,
  },
  lineItemRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: spacing.xs,
    borderBottomWidth: 1,
    borderBottomColor: colors.gray100,
  },
  lineItemDesc: {
    fontSize: typography.fontSize.sm,
    color: colors.text,
    flex: 1,
    marginRight: spacing.sm,
  },
  lineItemTotal: {
    fontSize: typography.fontSize.sm,
    color: colors.text,
    fontWeight: typography.fontWeight.medium,
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
  lineItemsSection: {
    marginTop: spacing.base,
    paddingTop: spacing.base,
    borderTopWidth: 1,
    borderTopColor: colors.gray200,
  },
  lineItemsSectionTitle: {
    fontSize: typography.fontSize.sm,
    fontWeight: typography.fontWeight.semibold,
    color: colors.gray700,
    marginBottom: spacing.sm,
  },
  reviewLineItem: {
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.gray100,
  },
  reviewLineItemHeader: {
    marginBottom: spacing.xs,
  },
  reviewLineItemDesc: {
    fontSize: typography.fontSize.sm,
    color: colors.text,
  },
  reviewLineItemDetails: {
    flexDirection: "row",
    justifyContent: "space-between",
  },
  reviewLineItemDetail: {
    fontSize: typography.fontSize.xs,
    color: colors.textSecondary,
  },
  reviewLineItemTotal: {
    fontSize: typography.fontSize.sm,
    color: colors.text,
    fontWeight: typography.fontWeight.medium,
  },
  totalsSection: {
    marginTop: spacing.base,
    paddingTop: spacing.base,
    borderTopWidth: 1,
    borderTopColor: colors.gray200,
  },
  totalRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: spacing.xs,
  },
  totalLabel: {
    fontSize: typography.fontSize.sm,
    color: colors.textSecondary,
  },
  totalValue: {
    fontSize: typography.fontSize.sm,
    color: colors.text,
  },
  grandTotalRow: {
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.gray200,
    marginTop: spacing.xs,
  },
  grandTotalLabel: {
    fontSize: typography.fontSize.base,
    fontWeight: typography.fontWeight.semibold,
    color: colors.gray800,
  },
  grandTotalValue: {
    fontSize: typography.fontSize.base,
    fontWeight: typography.fontWeight.bold,
    color: colors.success,
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
  contactSelectionSection: {
    marginBottom: spacing.lg,
  },
  dropdownButton: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    backgroundColor: colors.white,
    borderWidth: 1,
    borderColor: colors.gray300,
    borderRadius: 8,
    paddingHorizontal: spacing.base,
    paddingVertical: spacing.md,
    marginBottom: spacing.lg,
  },
  dropdownText: {
    fontSize: typography.fontSize.base,
    color: colors.textSecondary,
  },
  dropdownTextSelected: {
    fontSize: typography.fontSize.base,
    color: colors.text,
    fontWeight: typography.fontWeight.medium,
  },
  dropdownArrow: {
    fontSize: typography.fontSize.sm,
    color: colors.gray500,
  },
  orDivider: {
    textAlign: "center",
    color: colors.textSecondary,
    fontSize: typography.fontSize.sm,
    marginVertical: spacing.lg,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.5)",
    justifyContent: "flex-end",
  },
  modalContent: {
    backgroundColor: colors.white,
    borderTopLeftRadius: 16,
    borderTopRightRadius: 16,
    padding: spacing.lg,
    maxHeight: "70%",
  },
  modalTitle: {
    fontSize: typography.fontSize.lg,
    fontWeight: typography.fontWeight.semibold,
    color: colors.gray800,
    marginBottom: spacing.base,
    textAlign: "center",
  },
  contactList: {
    marginBottom: spacing.base,
  },
  contactItem: {
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.gray100,
  },
  contactName: {
    fontSize: typography.fontSize.base,
    fontWeight: typography.fontWeight.medium,
    color: colors.text,
  },
  contactEmail: {
    fontSize: typography.fontSize.sm,
    color: colors.textSecondary,
    marginTop: 2,
  },
  loadingText: {
    textAlign: "center",
    color: colors.textSecondary,
    marginVertical: spacing.lg,
  },
  noContactsText: {
    textAlign: "center",
    color: colors.textSecondary,
    marginBottom: spacing.lg,
    fontSize: typography.fontSize.sm,
  },
});
