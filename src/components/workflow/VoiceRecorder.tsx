/**
 * Voice recorder component with press-and-hold button.
 */

import React from "react";
import {
  View,
  Text,
  StyleSheet,
  Pressable,
  Animated,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import {
  colors,
  spacing,
  borderRadius,
  typography,
  shadows,
} from "../../constants/theme";
import { useVoiceRecording } from "../../hooks/useVoiceRecording";

interface VoiceRecorderProps {
  onRecordingComplete: (audioUri: string) => void;
  disabled?: boolean;
}

export default function VoiceRecorder({
  onRecordingComplete,
  disabled = false,
}: VoiceRecorderProps) {
  const {
    isRecording,
    isProcessing,
    hasRecorded,
    error,
    duration,
    startRecording,
    stopRecording,
    resetRecording,
  } = useVoiceRecording();

  const scaleAnim = React.useRef(new Animated.Value(1)).current;

  const handlePressIn = async () => {
    if (disabled || isProcessing) return;

    // Animate button scale
    Animated.spring(scaleAnim, {
      toValue: 0.95,
      useNativeDriver: true,
    }).start();

    await startRecording();
  };

  const handlePressOut = async () => {
    // Animate button scale back
    Animated.spring(scaleAnim, {
      toValue: 1,
      useNativeDriver: true,
    }).start();

    const audioUri = await stopRecording();
    if (audioUri) {
      onRecordingComplete(audioUri);
    }
  };

  const formatDuration = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  return (
    <View style={styles.container}>
      <Animated.View
        style={[styles.buttonWrapper, { transform: [{ scale: scaleAnim }] }]}
      >
        <Pressable
          onPressIn={handlePressIn}
          onPressOut={handlePressOut}
          disabled={disabled || isProcessing}
          style={[
            styles.button,
            isRecording && styles.buttonRecording,
            (disabled || isProcessing) && styles.buttonDisabled,
          ]}
        >
          <Ionicons
            name={isRecording ? "mic" : "mic-outline"}
            size={32}
            color={colors.white}
          />
        </Pressable>

        {/* Recording pulse animation */}
        {isRecording && (
          <View style={styles.pulseContainer}>
            <View style={[styles.pulse, styles.pulse1]} />
            <View style={[styles.pulse, styles.pulse2]} />
          </View>
        )}
      </Animated.View>

      {/* Status text */}
      <Text style={styles.statusText}>
        {isProcessing
          ? "Processing..."
          : isRecording
          ? `Recording ${formatDuration(duration)}`
          : hasRecorded
          ? "Hold to re-record"
          : "Hold to record"}
      </Text>

      {/* Error message */}
      {error && <Text style={styles.errorText}>{error}</Text>}

      {/* Re-record button */}
      {hasRecorded && !isRecording && !isProcessing && (
        <Pressable onPress={resetRecording} style={styles.resetButton}>
          <Text style={styles.resetText}>Clear recording</Text>
        </Pressable>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: "center",
    padding: spacing.lg,
  },
  buttonWrapper: {
    position: "relative",
    marginBottom: spacing.base,
  },
  button: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: colors.primary,
    justifyContent: "center",
    alignItems: "center",
    ...shadows.lg,
  },
  buttonRecording: {
    backgroundColor: colors.error,
  },
  buttonDisabled: {
    opacity: 0.5,
  },
  pulseContainer: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    justifyContent: "center",
    alignItems: "center",
  },
  pulse: {
    position: "absolute",
    width: 80,
    height: 80,
    borderRadius: 40,
    borderWidth: 2,
    borderColor: colors.error,
    opacity: 0.5,
  },
  pulse1: {
    // Animation would go here with Animated API
  },
  pulse2: {
    // Animation would go here with Animated API
  },
  statusText: {
    fontSize: typography.fontSize.base,
    color: colors.textSecondary,
    marginBottom: spacing.sm,
  },
  errorText: {
    fontSize: typography.fontSize.sm,
    color: colors.error,
    textAlign: "center",
    marginTop: spacing.sm,
  },
  resetButton: {
    marginTop: spacing.sm,
    padding: spacing.sm,
  },
  resetText: {
    fontSize: typography.fontSize.sm,
    color: colors.primary,
  },
});
