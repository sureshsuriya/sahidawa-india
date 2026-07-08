"use client";

import { useState, useRef, useCallback } from "react";
import {
    getPreferredRecordingMimeType,
    isRecordingBlobTooLarge,
    MAX_RECORDING_DURATION_MS,
} from "@/app/[locale]/voice/lib/recording";

const RECORDING_DURATION_LIMIT_MESSAGE =
    "Recording stopped after 60 seconds. Please keep voice checks under one minute.";
const RECORDING_SIZE_LIMIT_MESSAGE =
    "Recording is too large. Please record a shorter clip under 20MB.";

type VerificationResult = {
    medicine_name_original: string;
    medicine_name_english: string;
    medicine_name_regional: string;
    status: "verified" | "suspicious" | "not_found";
    manufacturer: string;
    category: string;
    cdsco_registered: boolean;
    warnings: string[];
    detected_language: string;
    script: string;
};

type ApiResponse = {
    success: boolean;
    transcribed: string;
    detected_language: string;
    script: string;
    verification: VerificationResult;
    error?: string;
};

interface UseVoiceVerificationReturn {
    isRecording: boolean;
    isLoading: boolean;
    audioLevel: number;
    result: ApiResponse | null;
    error: string | null;
    startRecording: () => Promise<void>;
    stopRecording: () => void;
    reset: () => void;
}

export function useVoiceVerification(): UseVoiceVerificationReturn {
    // States
    const [isRecording, setIsRecording] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [result, setResult] = useState<ApiResponse | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [audioLevel, setAudioLevel] = useState(0);

    // Refs
    const mediaRecorderRef = useRef<MediaRecorder | null>(null);
    const chunksRef = useRef<Blob[]>([]);
    const animFrameRef = useRef<number | null>(null);
    const analyserRef = useRef<AnalyserNode | null>(null);
    const recordingLimitTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    const clearRecordingLimitTimer = useCallback(() => {
        if (recordingLimitTimerRef.current) {
            clearTimeout(recordingLimitTimerRef.current);
            recordingLimitTimerRef.current = null;
        }
    }, []);

    // Send audio to API
    const sendAudioToApi = useCallback(async (blob: Blob) => {
        if (isRecordingBlobTooLarge(blob)) {
            setError(RECORDING_SIZE_LIMIT_MESSAGE);
            window.alert(RECORDING_SIZE_LIMIT_MESSAGE);
            return;
        }

        setIsLoading(true);
        setError(null);
        try {
            const form = new FormData();
            const ext = blob.type.includes("mp4") ? "mp4" : "webm";
            form.append("audio", blob, `recording.${ext}`);

            const res = await fetch("/api/medicine/verify-voice", {
                method: "POST",
                body: form,
            });

            const data: ApiResponse = await res.json();

            if (!res.ok || !data.success) {
                setError(data.error || "Verification failed. Please try again.");
            } else {
                setResult(data);
            }
        } catch {
            setError("Network error. Please check your connection and try again.");
        } finally {
            setIsLoading(false);
        }
    }, []);

    // Start recording
    const startRecording = useCallback(async () => {
        setError(null);
        setResult(null);
        clearRecordingLimitTimer();

        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

            // Visualize audio level
            const audioCtx = new AudioContext();
            const source = audioCtx.createMediaStreamSource(stream);
            const analyser = audioCtx.createAnalyser();
            analyser.fftSize = 256;
            source.connect(analyser);
            analyserRef.current = analyser;

            const draw = () => {
                const data = new Uint8Array(analyser.frequencyBinCount);
                analyser.getByteFrequencyData(data);
                const avg = data.reduce((a, b) => a + b, 0) / data.length;
                setAudioLevel(avg / 128);
                animFrameRef.current = requestAnimationFrame(draw);
            };
            draw();

            // Start MediaRecorder
            const mimeType = getPreferredRecordingMimeType(MediaRecorder);
            const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : {});
            chunksRef.current = [];

            recorder.ondataavailable = (e) => {
                if (e.data.size > 0) chunksRef.current.push(e.data);
            };

            recorder.onstop = async () => {
                clearRecordingLimitTimer();
                stream.getTracks().forEach((t) => t.stop());
                if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
                setAudioLevel(0);

                const blob = new Blob(chunksRef.current, { type: mimeType || "audio/webm" });
                await sendAudioToApi(blob);
            };

            recorder.start();
            mediaRecorderRef.current = recorder;
            setIsRecording(true);
            recordingLimitTimerRef.current = setTimeout(() => {
                if (recorder.state === "inactive") {
                    return;
                }

                setError(RECORDING_DURATION_LIMIT_MESSAGE);
                window.alert(RECORDING_DURATION_LIMIT_MESSAGE);
                recorder.stop();
                setIsRecording(false);
            }, MAX_RECORDING_DURATION_MS);
        } catch {
            clearRecordingLimitTimer();
            setError("Microphone access denied. Please allow microphone access and try again.");
        }
    }, [clearRecordingLimitTimer, sendAudioToApi]);

    // Stop recording
    const stopRecording = useCallback(() => {
        if (mediaRecorderRef.current && isRecording) {
            clearRecordingLimitTimer();
            mediaRecorderRef.current.stop();
            setIsRecording(false);
        }
    }, [clearRecordingLimitTimer, isRecording]);

    // Reset
    const reset = useCallback(() => {
        setResult(null);
        setError(null);
        setIsRecording(false);
        setIsLoading(false);
        setAudioLevel(0);
        clearRecordingLimitTimer();
    }, [clearRecordingLimitTimer]);

    return {
        isRecording,
        isLoading,
        audioLevel,
        result,
        error,
        startRecording,
        stopRecording,
        reset,
    };
}
