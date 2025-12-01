/**
 * Authentication screen with Xero OAuth and OpenAI API key validation.
 */

import React, { useState } from "react";
import {
  View,
  Text,
  TextInput,
  StyleSheet,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useAuth } from "../context/AuthContext";
import { colors, spacing, borderRadius, typography, shadows } from "../constants/theme";
import { Button, Card, LoadingSpinner } from "../components/common";

export default function AuthScreen() {
  const {
    isLoading,
    xeroConnected,
    openaiValid,
    error,
    startXeroAuth,
    validateOpenAIKey,
  } = useAuth();

  const [apiKey, setApiKey] = useState("");
  const [validating, setValidating] = useState(false);

  const handleValidateOpenAI = async () => {
    if (!apiKey.trim()) return;

    setValidating(true);
    await validateOpenAIKey(apiKey.trim());
    setValidating(false);
  };

  if (isLoading) {
    return <LoadingSpinner message="Loading..." />;
  }

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === "ios" ? "padding" : "height"}
    >
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        keyboardShouldPersistTaps="handled"
      >
        {/* Header */}
        <View style={styles.header}>
          <View style={styles.iconContainer}>
            <Ionicons name="mic" size={40} color={colors.primary} />
          </View>
          <Text style={styles.title}>Voice to Xero</Text>
          <Text style={styles.subtitle}>
            Create contacts and invoices using your voice
          </Text>
        </View>

        {/* Error message */}
        {error && (
          <Card style={styles.errorCard}>
            <View style={styles.errorContent}>
              <Ionicons name="alert-circle" size={20} color={colors.error} />
              <Text style={styles.errorText}>{error}</Text>
            </View>
          </Card>
        )}

        {/* Xero Connection Card */}
        <Card style={styles.authCard}>
          <View style={styles.cardHeader}>
            <View style={styles.cardTitleRow}>
              <Text style={styles.cardTitle}>Xero Connection</Text>
              {xeroConnected && (
                <View style={styles.statusBadge}>
                  <Ionicons
                    name="checkmark-circle"
                    size={16}
                    color={colors.success}
                  />
                  <Text style={styles.statusText}>Connected</Text>
                </View>
              )}
            </View>
            <Text style={styles.cardDescription}>
              Connect your Xero account to create contacts and invoices
            </Text>
          </View>

          {!xeroConnected ? (
            <Button
              title="Connect to Xero"
              onPress={startXeroAuth}
              loading={isLoading}
            />
          ) : (
            <View style={styles.connectedInfo}>
              <Ionicons name="business" size={24} color={colors.success} />
              <Text style={styles.connectedText}>
                Your Xero account is connected
              </Text>
            </View>
          )}
        </Card>

        {/* OpenAI API Key Card */}
        <Card style={styles.authCard}>
          <View style={styles.cardHeader}>
            <View style={styles.cardTitleRow}>
              <Text style={styles.cardTitle}>OpenAI API Key</Text>
              {openaiValid && (
                <View style={styles.statusBadge}>
                  <Ionicons
                    name="checkmark-circle"
                    size={16}
                    color={colors.success}
                  />
                  <Text style={styles.statusText}>Validated</Text>
                </View>
              )}
            </View>
            <Text style={styles.cardDescription}>
              Enter your OpenAI API key for voice transcription
            </Text>
          </View>

          {!openaiValid ? (
            <View style={styles.inputContainer}>
              <TextInput
                style={styles.input}
                placeholder="sk-..."
                placeholderTextColor={colors.gray400}
                value={apiKey}
                onChangeText={setApiKey}
                secureTextEntry
                autoCapitalize="none"
                autoCorrect={false}
              />
              <Button
                title="Validate"
                onPress={handleValidateOpenAI}
                loading={validating}
                disabled={!apiKey.trim()}
              />
            </View>
          ) : (
            <View style={styles.connectedInfo}>
              <Ionicons name="key" size={24} color={colors.success} />
              <Text style={styles.connectedText}>
                Your API key is validated
              </Text>
            </View>
          )}
        </Card>

        {/* Ready message */}
        {xeroConnected && openaiValid && (
          <Card style={styles.readyCard}>
            <Ionicons
              name="checkmark-circle"
              size={32}
              color={colors.success}
            />
            <Text style={styles.readyTitle}>You're all set!</Text>
            <Text style={styles.readyText}>
              You can now create contacts and invoices using your voice.
            </Text>
          </Card>
        )}

        {/* Info section */}
        <View style={styles.infoSection}>
          <Text style={styles.infoTitle}>Why do I need these?</Text>
          <View style={styles.infoItem}>
            <Ionicons name="shield-checkmark" size={18} color={colors.gray500} />
            <Text style={styles.infoText}>
              Xero: To create contacts and invoices in your account
            </Text>
          </View>
          <View style={styles.infoItem}>
            <Ionicons name="mic" size={18} color={colors.gray500} />
            <Text style={styles.infoText}>
              OpenAI: To transcribe and understand your voice commands
            </Text>
          </View>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  scrollContent: {
    padding: spacing.base,
    paddingBottom: spacing["3xl"],
  },
  header: {
    alignItems: "center",
    marginBottom: spacing.xl,
    marginTop: spacing.lg,
  },
  iconContainer: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: colors.gray100,
    justifyContent: "center",
    alignItems: "center",
    marginBottom: spacing.base,
  },
  title: {
    fontSize: typography.fontSize["2xl"],
    fontWeight: typography.fontWeight.bold,
    color: colors.gray900,
    marginBottom: spacing.xs,
  },
  subtitle: {
    fontSize: typography.fontSize.base,
    color: colors.textSecondary,
    textAlign: "center",
  },
  errorCard: {
    backgroundColor: "#FEE2E2",
    marginBottom: spacing.base,
  },
  errorContent: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  errorText: {
    color: colors.error,
    fontSize: typography.fontSize.sm,
    flex: 1,
  },
  authCard: {
    marginBottom: spacing.base,
  },
  cardHeader: {
    marginBottom: spacing.base,
  },
  cardTitleRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.xs,
  },
  cardTitle: {
    fontSize: typography.fontSize.lg,
    fontWeight: typography.fontWeight.semibold,
    color: colors.gray800,
  },
  statusBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    backgroundColor: "#ECFDF5",
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    borderRadius: borderRadius.full,
  },
  statusText: {
    fontSize: typography.fontSize.xs,
    color: colors.success,
    fontWeight: typography.fontWeight.medium,
  },
  cardDescription: {
    fontSize: typography.fontSize.sm,
    color: colors.textSecondary,
  },
  connectedInfo: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    padding: spacing.md,
    backgroundColor: colors.gray50,
    borderRadius: borderRadius.md,
  },
  connectedText: {
    fontSize: typography.fontSize.sm,
    color: colors.success,
    fontWeight: typography.fontWeight.medium,
  },
  inputContainer: {
    gap: spacing.sm,
  },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.base,
    fontSize: typography.fontSize.base,
    color: colors.text,
    backgroundColor: colors.surface,
  },
  readyCard: {
    alignItems: "center",
    backgroundColor: "#ECFDF5",
    marginBottom: spacing.base,
  },
  readyTitle: {
    fontSize: typography.fontSize.lg,
    fontWeight: typography.fontWeight.semibold,
    color: colors.success,
    marginTop: spacing.sm,
  },
  readyText: {
    fontSize: typography.fontSize.sm,
    color: colors.gray600,
    textAlign: "center",
    marginTop: spacing.xs,
  },
  infoSection: {
    padding: spacing.base,
  },
  infoTitle: {
    fontSize: typography.fontSize.sm,
    fontWeight: typography.fontWeight.medium,
    color: colors.gray600,
    marginBottom: spacing.sm,
  },
  infoItem: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },
  infoText: {
    fontSize: typography.fontSize.sm,
    color: colors.gray500,
    flex: 1,
  },
});
