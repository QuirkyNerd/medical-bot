export type Provider = "groq";

export type ChatMessage = {
  role: "user" | "assistant" | "system";
  content: string;
};

/**
 * groq-best  → llama-3.3-70b-versatile  (primary, highest quality)
 * groq-fast  → llama-3.1-8b-instant      (fallback, ultra-low latency)
 */
export type Preset = "groq-best" | "groq-fast";

export type MedicalContextPayload = {
  country: string;
  language: string;
  emergencyNumber: string;
  units?: "metric" | "imperial";
};

export type ChatRequest = {
  preset?: Preset;
  provider?: Provider;
  model?: string;
  apiKey?: string;
  context?: MedicalContextPayload;
  messages: ChatMessage[];
  stream?: boolean;
};

export type ProviderConfig = {
  name: string;
  displayName: string;
  requiresApiKey: boolean;
  models: { id: string; name: string }[];
};

export const PROVIDER_CONFIGS: Record<Provider, ProviderConfig> = {
  groq: {
    name: "groq",
    displayName: "Groq (Llama 3.3 · Fastest)",
    requiresApiKey: true,
    models: [
      { id: "llama-3.3-70b-versatile", name: "Llama 3.3 70B Versatile (recommended)" },
      { id: "llama-3.1-8b-instant",    name: "Llama 3.1 8B Instant (fastest)" },
    ],
  },
};
