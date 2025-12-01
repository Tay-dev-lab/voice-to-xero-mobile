/**
 * App navigation configuration.
 */

import React from "react";
import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";

import { useAuth } from "../context/AuthContext";
import { colors } from "../constants/theme";

// Import screens (to be created)
import AuthScreen from "../screens/AuthScreen";
import HomeScreen from "../screens/HomeScreen";
import ContactWorkflowScreen from "../screens/ContactWorkflow";
import InvoiceWorkflowScreen from "../screens/InvoiceWorkflow";

// Stack param list type
export type RootStackParamList = {
  Auth: undefined;
  Home: undefined;
  ContactWorkflow: { sessionId?: string } | undefined;
  InvoiceWorkflow: { sessionId?: string } | undefined;
};

const Stack = createNativeStackNavigator<RootStackParamList>();

export default function AppNavigator() {
  const { isAuthenticated, xeroConnected, openaiValid } = useAuth();

  // User is ready when both Xero and OpenAI are connected
  const isReady = xeroConnected && openaiValid;

  return (
    <NavigationContainer>
      <Stack.Navigator
        screenOptions={{
          headerStyle: {
            backgroundColor: colors.surface,
          },
          headerTintColor: colors.gray800,
          headerTitleStyle: {
            fontWeight: "600",
          },
          headerShadowVisible: false,
          contentStyle: {
            backgroundColor: colors.background,
          },
        }}
      >
        {!isAuthenticated || !isReady ? (
          // Auth flow
          <Stack.Screen
            name="Auth"
            component={AuthScreen}
            options={{
              title: "Voice to Xero",
              headerShown: true,
            }}
          />
        ) : (
          // Main app flow
          <>
            <Stack.Screen
              name="Home"
              component={HomeScreen}
              options={{
                title: "Voice to Xero",
              }}
            />
            <Stack.Screen
              name="ContactWorkflow"
              component={ContactWorkflowScreen}
              options={{
                title: "Add Contact",
                headerBackTitle: "Back",
              }}
            />
            <Stack.Screen
              name="InvoiceWorkflow"
              component={InvoiceWorkflowScreen}
              options={{
                title: "Create Invoice",
                headerBackTitle: "Back",
              }}
            />
          </>
        )}
      </Stack.Navigator>
    </NavigationContainer>
  );
}
