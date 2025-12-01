/**
 * Card container component.
 */

import React, { ReactNode } from "react";
import { View, StyleSheet, ViewStyle } from "react-native";
import { colors, spacing, borderRadius, shadows } from "../../constants/theme";

interface CardProps {
  children: ReactNode;
  style?: ViewStyle;
  variant?: "default" | "outlined";
}

export default function Card({
  children,
  style,
  variant = "default",
}: CardProps) {
  return (
    <View
      style={[styles.card, variant === "outlined" && styles.outlined, style]}
    >
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    padding: spacing.base,
    ...shadows.md,
  },
  outlined: {
    ...shadows.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
});
