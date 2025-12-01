/**
 * Home screen with workflow selection.
 */

import React from "react";
import { View, Text, StyleSheet, ScrollView } from "react-native";
import { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { Ionicons } from "@expo/vector-icons";
import { RootStackParamList } from "../navigation/AppNavigator";
import { useAuth } from "../context/AuthContext";
import { colors, spacing, typography } from "../constants/theme";
import { Button, Card } from "../components/common";

type HomeScreenNavigationProp = NativeStackNavigationProp<
  RootStackParamList,
  "Home"
>;

interface HomeScreenProps {
  navigation: HomeScreenNavigationProp;
}

export default function HomeScreen({ navigation }: HomeScreenProps) {
  const { logout } = useAuth();

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Welcome section */}
      <View style={styles.header}>
        <Text style={styles.greeting}>Welcome!</Text>
        <Text style={styles.subtitle}>What would you like to do today?</Text>
      </View>

      {/* Workflow cards */}
      <View style={styles.cards}>
        {/* Add Contact */}
        <Card style={styles.workflowCard}>
          <View style={styles.cardIcon}>
            <Ionicons name="person-add" size={32} color={colors.primary} />
          </View>
          <Text style={styles.cardTitle}>Add New Contact</Text>
          <Text style={styles.cardDescription}>
            Create a new contact in Xero by speaking their details
          </Text>
          <Button
            title="Start"
            onPress={() => navigation.navigate("ContactWorkflow")}
            style={styles.cardButton}
          />
        </Card>

        {/* Create Invoice */}
        <Card style={styles.workflowCard}>
          <View style={styles.cardIcon}>
            <Ionicons name="document-text" size={32} color={colors.success} />
          </View>
          <Text style={styles.cardTitle}>Create Invoice</Text>
          <Text style={styles.cardDescription}>
            Generate and send an invoice by speaking the details
          </Text>
          <Button
            title="Start"
            onPress={() => navigation.navigate("InvoiceWorkflow")}
            variant="success"
            style={styles.cardButton}
          />
        </Card>
      </View>

      {/* Quick tips */}
      <View style={styles.tipsSection}>
        <Text style={styles.tipsTitle}>Quick Tips</Text>
        <View style={styles.tipItem}>
          <Ionicons name="mic" size={18} color={colors.gray500} />
          <Text style={styles.tipText}>
            Hold the microphone button while speaking
          </Text>
        </View>
        <View style={styles.tipItem}>
          <Ionicons name="refresh" size={18} color={colors.gray500} />
          <Text style={styles.tipText}>
            You can re-record if we didn't get it right
          </Text>
        </View>
        <View style={styles.tipItem}>
          <Ionicons name="create" size={18} color={colors.gray500} />
          <Text style={styles.tipText}>
            Edit any field before submitting to Xero
          </Text>
        </View>
      </View>

      {/* Logout */}
      <View style={styles.footer}>
        <Button title="Logout" onPress={logout} variant="outline" />
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: spacing.base,
    paddingBottom: spacing["3xl"],
  },
  header: {
    marginBottom: spacing.xl,
    marginTop: spacing.base,
  },
  greeting: {
    fontSize: typography.fontSize["2xl"],
    fontWeight: typography.fontWeight.bold,
    color: colors.gray900,
    marginBottom: spacing.xs,
  },
  subtitle: {
    fontSize: typography.fontSize.base,
    color: colors.textSecondary,
  },
  cards: {
    gap: spacing.base,
    marginBottom: spacing.xl,
  },
  workflowCard: {
    alignItems: "center",
    paddingVertical: spacing.xl,
  },
  cardIcon: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: colors.gray50,
    justifyContent: "center",
    alignItems: "center",
    marginBottom: spacing.base,
  },
  cardTitle: {
    fontSize: typography.fontSize.lg,
    fontWeight: typography.fontWeight.semibold,
    color: colors.gray800,
    marginBottom: spacing.xs,
  },
  cardDescription: {
    fontSize: typography.fontSize.sm,
    color: colors.textSecondary,
    textAlign: "center",
    marginBottom: spacing.base,
    paddingHorizontal: spacing.base,
  },
  cardButton: {
    minWidth: 120,
  },
  tipsSection: {
    padding: spacing.base,
    backgroundColor: colors.gray50,
    borderRadius: 12,
    marginBottom: spacing.xl,
  },
  tipsTitle: {
    fontSize: typography.fontSize.sm,
    fontWeight: typography.fontWeight.semibold,
    color: colors.gray700,
    marginBottom: spacing.sm,
  },
  tipItem: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },
  tipText: {
    fontSize: typography.fontSize.sm,
    color: colors.gray600,
    flex: 1,
  },
  footer: {
    marginTop: spacing.base,
  },
});
