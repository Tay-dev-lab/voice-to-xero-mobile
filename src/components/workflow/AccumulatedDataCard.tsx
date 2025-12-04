/**
 * Accumulated data card component for displaying previously entered workflow data.
 * Supports inline editing by tapping on editable fields.
 */

import React from "react";
import { View, Text, StyleSheet, TouchableOpacity } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { colors, spacing, typography, borderRadius } from "../../constants/theme";

interface DataField {
  label: string;
  value: string;
  fieldName: string;
  editable?: boolean;
}

interface AccumulatedDataCardProps {
  data: DataField[];
  onEditField?: (fieldName: string, currentValue: string) => void;
  title?: string;
}

export default function AccumulatedDataCard({
  data,
  onEditField,
  title,
}: AccumulatedDataCardProps) {
  if (!data || data.length === 0) return null;

  // Filter out empty values
  const validData = data.filter((item) => item.value && item.value.trim() !== "");
  if (validData.length === 0) return null;

  return (
    <View style={styles.container}>
      {title && <Text style={styles.title}>{title}</Text>}
      {validData.map((item, index) => {
        const isLastItem = index === validData.length - 1;
        const canEdit = item.editable !== false && onEditField;

        return (
          <TouchableOpacity
            key={item.fieldName}
            style={[styles.row, isLastItem && styles.lastRow]}
            onPress={() => canEdit && onEditField(item.fieldName, item.value)}
            disabled={!canEdit}
            activeOpacity={canEdit ? 0.7 : 1}
          >
            <Text style={styles.label}>{item.label}</Text>
            <View style={styles.valueContainer}>
              <Text style={styles.value} numberOfLines={1}>
                {item.value}
              </Text>
              {canEdit && (
                <Ionicons
                  name="pencil"
                  size={14}
                  color={colors.primary}
                  style={styles.editIcon}
                />
              )}
            </View>
          </TouchableOpacity>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: colors.gray50,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginBottom: spacing.base,
    borderWidth: 1,
    borderColor: colors.gray200,
  },
  title: {
    fontSize: typography.fontSize.sm,
    fontWeight: typography.fontWeight.semibold,
    color: colors.text,
    marginBottom: spacing.sm,
  },
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.gray200,
  },
  lastRow: {
    borderBottomWidth: 0,
  },
  label: {
    fontSize: typography.fontSize.sm,
    color: colors.textSecondary,
    flex: 0.4,
  },
  valueContainer: {
    flexDirection: "row",
    alignItems: "center",
    flex: 0.6,
    justifyContent: "flex-end",
  },
  value: {
    fontSize: typography.fontSize.base,
    color: colors.text,
    fontWeight: typography.fontWeight.medium,
    textAlign: "right",
    flexShrink: 1,
  },
  editIcon: {
    marginLeft: spacing.sm,
  },
});
