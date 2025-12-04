/**
 * Navigation buttons component for workflow back/forward navigation.
 * Back button: visible when not on first step
 * Forward button: visible when returning to a previously completed step
 */

import React from "react";
import { View, Text, StyleSheet, TouchableOpacity } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { colors, spacing, typography, borderRadius } from "../../constants/theme";

interface NavigationButtonsProps {
  currentStepIndex: number;
  totalSteps: number;
  completedSteps: string[];
  steps: string[];
  onBack: () => void;
  onForward: () => void;
  disabled?: boolean;
}

export default function NavigationButtons({
  currentStepIndex,
  totalSteps,
  completedSteps,
  steps,
  onBack,
  onForward,
  disabled = false,
}: NavigationButtonsProps) {
  // Back button visible when not on first step
  const showBackButton = currentStepIndex > 0;

  // Forward button visible when:
  // 1. Not on last step
  // 2. Current step is already completed (meaning user navigated back to it)
  const currentStep = steps[currentStepIndex];
  const showForwardButton =
    currentStepIndex < totalSteps - 1 && completedSteps.includes(currentStep);

  // Don't render if no buttons to show
  if (!showBackButton && !showForwardButton) {
    return null;
  }

  return (
    <View style={styles.container}>
      {/* Back button */}
      {showBackButton ? (
        <TouchableOpacity
          style={[styles.button, disabled && styles.buttonDisabled]}
          onPress={onBack}
          disabled={disabled}
          activeOpacity={0.7}
        >
          <Ionicons
            name="chevron-back"
            size={20}
            color={disabled ? colors.gray400 : colors.primary}
          />
          <Text style={[styles.buttonText, disabled && styles.buttonTextDisabled]}>
            Back
          </Text>
        </TouchableOpacity>
      ) : (
        <View style={styles.placeholder} />
      )}

      {/* Forward button */}
      {showForwardButton ? (
        <TouchableOpacity
          style={[styles.button, disabled && styles.buttonDisabled]}
          onPress={onForward}
          disabled={disabled}
          activeOpacity={0.7}
        >
          <Text style={[styles.buttonText, disabled && styles.buttonTextDisabled]}>
            Forward
          </Text>
          <Ionicons
            name="chevron-forward"
            size={20}
            color={disabled ? colors.gray400 : colors.primary}
          />
        </TouchableOpacity>
      ) : (
        <View style={styles.placeholder} />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: spacing.base,
    paddingVertical: spacing.md,
    marginTop: spacing.base,
    borderTopWidth: 1,
    borderTopColor: colors.gray200,
  },
  button: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: borderRadius.md,
    backgroundColor: colors.gray50,
    borderWidth: 1,
    borderColor: colors.gray200,
  },
  buttonDisabled: {
    opacity: 0.5,
  },
  buttonText: {
    fontSize: typography.fontSize.base,
    color: colors.primary,
    fontWeight: typography.fontWeight.medium,
    marginHorizontal: spacing.xs,
  },
  buttonTextDisabled: {
    color: colors.gray400,
  },
  placeholder: {
    width: 80,
  },
});
