/**
 * Step progress indicator component.
 */

import React from "react";
import { View, Text, StyleSheet, TouchableOpacity } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { colors, spacing, typography } from "../../constants/theme";

interface Step {
  name: string;
  label: string;
}

interface StepProgressProps {
  steps: Step[];
  currentStep: string;
  completedSteps: string[];
  onStepPress?: (stepName: string) => void;
}

export default function StepProgress({
  steps,
  currentStep,
  completedSteps,
  onStepPress,
}: StepProgressProps) {
  const getStepStatus = (
    stepName: string
  ): "completed" | "current" | "pending" => {
    if (completedSteps.includes(stepName)) return "completed";
    if (stepName === currentStep) return "current";
    return "pending";
  };

  const isStepClickable = (stepName: string): boolean => {
    return completedSteps.includes(stepName) && onStepPress !== undefined;
  };

  return (
    <View style={styles.container}>
      {steps.map((step, index) => {
        const status = getStepStatus(step.name);
        const clickable = isStepClickable(step.name);

        return (
          <React.Fragment key={step.name}>
            <TouchableOpacity
              onPress={() => clickable && onStepPress?.(step.name)}
              disabled={!clickable}
              style={styles.stepContainer}
              activeOpacity={clickable ? 0.7 : 1}
            >
              <View
                style={[
                  styles.stepCircle,
                  status === "completed" && styles.stepCompleted,
                  status === "current" && styles.stepCurrent,
                  status === "pending" && styles.stepPending,
                ]}
              >
                {status === "completed" ? (
                  <Ionicons
                    name="checkmark"
                    size={14}
                    color={colors.white}
                  />
                ) : (
                  <Text
                    style={[
                      styles.stepNumber,
                      status === "current" && styles.stepNumberCurrent,
                    ]}
                  >
                    {index + 1}
                  </Text>
                )}
              </View>
              <Text
                style={[
                  styles.stepLabel,
                  status === "current" && styles.stepLabelCurrent,
                  status === "completed" && styles.stepLabelCompleted,
                ]}
                numberOfLines={1}
              >
                {step.label}
              </Text>
            </TouchableOpacity>

            {/* Connector line */}
            {index < steps.length - 1 && (
              <View
                style={[
                  styles.connector,
                  completedSteps.includes(step.name) &&
                    styles.connectorCompleted,
                ]}
              />
            )}
          </React.Fragment>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: spacing.base,
    paddingHorizontal: spacing.sm,
  },
  stepContainer: {
    alignItems: "center",
    minWidth: 50,
  },
  stepCircle: {
    width: 28,
    height: 28,
    borderRadius: 14,
    justifyContent: "center",
    alignItems: "center",
    marginBottom: spacing.xs,
  },
  stepCompleted: {
    backgroundColor: colors.success,
  },
  stepCurrent: {
    backgroundColor: colors.primary,
  },
  stepPending: {
    backgroundColor: colors.gray200,
  },
  stepNumber: {
    fontSize: typography.fontSize.sm,
    fontWeight: typography.fontWeight.semibold,
    color: colors.gray500,
  },
  stepNumberCurrent: {
    color: colors.white,
  },
  stepLabel: {
    fontSize: typography.fontSize.xs,
    color: colors.textSecondary,
    textAlign: "center",
  },
  stepLabelCurrent: {
    color: colors.primary,
    fontWeight: typography.fontWeight.medium,
  },
  stepLabelCompleted: {
    color: colors.success,
  },
  connector: {
    flex: 1,
    height: 2,
    backgroundColor: colors.gray200,
    marginHorizontal: spacing.xs,
    marginBottom: spacing.lg,
  },
  connectorCompleted: {
    backgroundColor: colors.success,
  },
});
