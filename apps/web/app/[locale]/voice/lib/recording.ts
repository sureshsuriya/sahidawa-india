const PREFERRED_RECORDING_TYPES = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"] as const;
export const MAX_RECORDING_DURATION_MS = 60_000;
export const MAX_RECORDING_SIZE_BYTES = 20 * 1024 * 1024;

type MediaRecorderConstructorLike = {
    isTypeSupported?: (mimeType: string) => boolean;
};

export function supportsAudioRecording(targetWindow: Window): boolean {
    return (
        "MediaRecorder" in targetWindow &&
        typeof (targetWindow as Window & { MediaRecorder?: unknown }).MediaRecorder === "function"
    );
}

export function getPreferredRecordingMimeType(
    recorderConstructor: MediaRecorderConstructorLike | null
): string {
    if (!recorderConstructor?.isTypeSupported) {
        return "";
    }

    return (
        PREFERRED_RECORDING_TYPES.find((mimeType) =>
            recorderConstructor.isTypeSupported?.(mimeType)
        ) ?? ""
    );
}

export function isRecordingBlobTooLarge(blob: Blob): boolean {
    return blob.size > MAX_RECORDING_SIZE_BYTES;
}
