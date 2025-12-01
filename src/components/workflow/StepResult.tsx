/**
 * Step result display component.
 */

import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { colors, spacing, borderRadius, typography } from "../../constants/theme";
import Card from "../common/Card";
import Button from "../common/Button";

interface StepResultProps {
  transcript: string;
  parsedData: Record<string, unknown>;
  onContinue: () => void;
  onReRecord?: () => void;
  loading?: boolean;
}

export default function StepResult({
  transcript,
  parsedData,
  onContinue,
  onReRecord,
  loading = false,
}: StepResultProps) {
  const formatValue = (value: unknown): string => {
    if (value === null || value === undefined) return "-";
    if (typeof value === "boolean") return value ? "Yes" : "No";
    if (typeof value === "object") return JSON.stringify(value);
    return String(value);
  };

  return (
    <View style={styles.container}>
      {/* Transcript */}
      <Card style={styles.transcriptCard}>
        <View style={styles.transcriptHeader}>
          <Ionicons name="mic" size={18} color={colors.primary} />
          <Text style={styles.transcriptLabel}>You said:</Text>
        </View>
        <Text style={styles.transcriptText}>"{transcript}"</Text>
      </Card>

      {/* Parsed Data */}
      <Card style={styles.dataCard}>
        <View style={styles.dataHeader}>
          <Ionicons name="checkmark-circle" size={18} color={colors.success} />
          <Text style={styles.dataLabel}>We understood:</Text>
        </View>
        <View style={styles.dataList}>
          {Object.entries(parsedData).map(([key, value]) => (
            <View key={key} style={styles.dataRow}>
              <Text style={styles.dataKey}>
                {key.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase())}
              </Text>
              <Text style={styles.dataValue}>{formatValue(value)}</Text>
            </View>
          ))}
        </View>
      </Card>

      {/* Action buttons */}
      <View style={styles.actions}>
        <Button
          title="Continue"
          onPress={onContinue}
          loading={loading}
          style={styles.continueButton}
        />
        {onReRecord && (
          <Button
            title="Re-record"
            onPress={onReRecord}
            variant="outline"
            disabled={loading}
          />
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: spacing.base,
  },
  transcriptCard: {
    backgroundColor: colors.gray50,
  },
  transcriptHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },
  transcriptLabel: {
    fontSize: typography.fontSize.sm,
    color: colors.textSecondary,
    fontWeight: typography.fontWeight.medium,
  },
  transcriptText: {
    fontSize: typography.fontSize.base,
    color: colors.text,
    fontStyle: "italic",
  },
  dataCard: {},
  dataHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
  dataLabel: {
    fontSize: typography.fontSize.sm,
    color: colors.textSecondary,
    fontWeight: typography.fontWeight.medium,
  },
  dataList: {
    gap: spacing.sm,
  },
  dataRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: spacing.xs,
    borderBottomWidth: 1,
    borderBottomColor: colors.gray100,
  },
  dataKey: {
    fontSize: typography.fontSize.sm,
    color: colors.textSecondary,
    flex: 1,
  },
  dataValue: {
    fontSize: typography.fontSize.sm,
    color: colors.text,
    fontWeight: typography.fontWeight.medium,
    flex: 2,
    textAlign: "right",
  },
  actions: {
    gap: spacing.sm,
    marginTop: spacing.sm,
  },
  continueButton: {
    // Full width
  },
});
