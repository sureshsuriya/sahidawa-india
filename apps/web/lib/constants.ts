export const ChatRoles = {
    USER: "user",
    MODEL: "model",
    ASSISTANT: "assistant",
} as const;

export type ChatRole = typeof ChatRoles[keyof typeof ChatRoles];