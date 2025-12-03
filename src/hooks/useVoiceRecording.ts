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
  // Track if stop was requested while start was in progress
  const stopRequestedRef = useRef(false);

  /**
   * Request microphone permission and start recording.
   */
  const startRecording = useCallback(async () => {
    // Guard: Don't start if already recording or processing
    if (recordingRef.current || state.isRecording || state.isProcessing) {
      console.log("Recording already in progress, ignoring start request");
      return;
    }

    // Reset stop request flag
    stopRequestedRef.current = false;

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

      // Check if stop was requested during permission request
      if (stopRequestedRef.current) {
        setState((prev) => ({ ...prev, isProcessing: false }));
        return;
      }

      // Set audio mode for recording
      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
      });

      // Check if stop was requested during audio mode setup
      if (stopRequestedRef.current) {
        await Audio.setAudioModeAsync({ allowsRecordingIOS: false });
        setState((prev) => ({ ...prev, isProcessing: false }));
        return;
      }

      // Create and start recording
      const { recording } = await Audio.Recording.createAsync(
        Audio.RecordingOptionsPresets.HIGH_QUALITY
      );

      recordingRef.current = recording;

      // Check if stop was requested during recording creation
      if (stopRequestedRef.current) {
        console.log("Stop requested during recording creation, stopping immediately");
        await recording.stopAndUnloadAsync();
        await Audio.setAudioModeAsync({ allowsRecordingIOS: false });
        recordingRef.current = null;
        setState((prev) => ({ ...prev, isProcessing: false }));
        return;
      }

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
      // Clean up any partial state
      recordingRef.current = null;
      setState((prev) => ({
        ...prev,
        isRecording: false,
        isProcessing: false,
        error:
          error instanceof Error
            ? error.message
            : "Failed to start recording",
      }));
    }
  }, [state.isRecording, state.isProcessing]);

  /**
   * Stop recording and return audio file URI.
   */
  const stopRecording = useCallback(async (): Promise<string | null> => {
    // Clear duration interval first
    if (durationIntervalRef.current) {
      clearInterval(durationIntervalRef.current);
      durationIntervalRef.current = null;
    }

    // Guard: Nothing to stop yet - signal to startRecording to abort
    if (!recordingRef.current) {
      // Set flag so startRecording knows to abort if it's still in progress
      stopRequestedRef.current = true;
      setState((prev) => ({
        ...prev,
        isRecording: false,
        isProcessing: false,
      }));
      return null;
    }

    try {
      setState((prev) => ({ ...prev, isProcessing: true }));

      // Get reference and clear it immediately to prevent double-stop
      const recording = recordingRef.current;
      recordingRef.current = null;

      // Stop recording
      await recording.stopAndUnloadAsync();

      // Haptic feedback
      await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);

      // Get URI
      const uri = recording.getURI();

      // Reset audio mode
      await Audio.setAudioModeAsync({
        allowsRecordingIOS: false,
      });

      setState((prev) => ({
        ...prev,
        isRecording: false,
        isProcessing: false,
        hasRecorded: uri !== null,
        audioUri: uri,
      }));

      return uri;
    } catch (error) {
      console.error("Failed to stop recording:", error);
      recordingRef.current = null;
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
