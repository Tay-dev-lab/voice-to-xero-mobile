/**
 * Voice recording hook using expo-av.
 * Replaces browser MediaRecorder API functionality.
 */

import { useState, useCallback, useRef } from "react";
import { Audio } from "expo-av";
import * as Haptics from "expo-haptics";

interface VoiceRecordingState {
  isRecording: boolean;
  isProcessing: boolean;
  hasRecorded: boolean;
  audioUri: string | null;
  error: string | null;
  duration: number;
}

interface UseVoiceRecordingReturn extends VoiceRecordingState {
  startRecording: () => Promise<void>;
  stopRecording: () => Promise<string | null>;
  resetRecording: () => void;
}

export function useVoiceRecording(): UseVoiceRecordingReturn {
  const [state, setState] = useState<VoiceRecordingState>({
    isRecording: false,
    isProcessing: false,
    hasRecorded: false,
    audioUri: null,
    error: null,
    duration: 0,
  });

  const recordingRef = useRef<Audio.Recording | null>(null);
  const durationIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  /**
   * Request microphone permission and start recording.
   */
  const startRecording = useCallback(async () => {
    try {
      setState((prev) => ({ ...prev, error: null, isProcessing: true }));

      // Request permission
      const permission = await Audio.requestPermissionsAsync();
      if (!permission.granted) {
        setState((prev) => ({
          ...prev,
          isProcessing: false,
          error: "Microphone permission denied. Please enable in settings.",
        }));
        return;
      }

      // Set audio mode for recording
      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
      });

      // Create and start recording
      const { recording } = await Audio.Recording.createAsync(
        Audio.RecordingOptionsPresets.HIGH_QUALITY
      );

      recordingRef.current = recording;

      // Haptic feedback
      await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);

      // Start duration counter
      const startTime = Date.now();
      durationIntervalRef.current = setInterval(() => {
        setState((prev) => ({
          ...prev,
          duration: Math.floor((Date.now() - startTime) / 1000),
        }));
      }, 100);

      setState((prev) => ({
        ...prev,
        isRecording: true,
        isProcessing: false,
        duration: 0,
      }));
    } catch (error) {
      console.error("Failed to start recording:", error);
      setState((prev) => ({
        ...prev,
        isProcessing: false,
        error:
          error instanceof Error
            ? error.message
            : "Failed to start recording",
      }));
    }
  }, []);

  /**
   * Stop recording and return audio file URI.
   */
  const stopRecording = useCallback(async (): Promise<string | null> => {
    if (!recordingRef.current) {
      return null;
    }

    try {
      setState((prev) => ({ ...prev, isProcessing: true }));

      // Clear duration interval
      if (durationIntervalRef.current) {
        clearInterval(durationIntervalRef.current);
        durationIntervalRef.current = null;
      }

      // Stop recording
      await recordingRef.current.stopAndUnloadAsync();

      // Haptic feedback
      await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);

      // Get URI
      const uri = recordingRef.current.getURI();
      recordingRef.current = null;

      // Reset audio mode
      await Audio.setAudioModeAsync({
        allowsRecordingIOS: false,
      });

      setState((prev) => ({
        ...prev,
        isRecording: false,
        isProcessing: false,
        hasRecorded: true,
        audioUri: uri,
      }));

      return uri;
    } catch (error) {
      console.error("Failed to stop recording:", error);
      setState((prev) => ({
        ...prev,
        isRecording: false,
        isProcessing: false,
        error:
          error instanceof Error ? error.message : "Failed to stop recording",
      }));
      return null;
    }
  }, []);

  /**
   * Reset recording state for new recording.
   */
  const resetRecording = useCallback(() => {
    setState({
      isRecording: false,
      isProcessing: false,
      hasRecorded: false,
      audioUri: null,
      error: null,
      duration: 0,
    });
  }, []);

  return {
    ...state,
    startRecording,
    stopRecording,
    resetRecording,
  };
}
