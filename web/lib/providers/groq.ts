/**
 * Groq provider — OpenAI-compatible API, ultra-fast inference.
 *
 * Uses the `openai` SDK (already a dependency) pointed at Groq's base URL.
 * Server-side only: GROQ_API_KEY is never exposed to the browser.
 *
 * Primary model  : llama-3.3-70b-versatile  (best quality, ~275 tok/s)
 * Fallback model : llama-3.1-8b-instant     (fastest,      ~800 tok/s)
 *
 * Free tier: https://console.groq.com — 100K tokens / day, no credit card.
 */
import OpenAI from "openai";
import type { ChatMessage } from "../types";
import { resolveSystemPrompt, type MedicalContext } from "./system-prompt";

const GROQ_BASE_URL = "https://api.groq.com/openai/v1";

/** Default model used when none is specified for this provider. */
export const GROQ_DEFAULT_MODEL = "llama-3.3-70b-versatile";

function getClient(userApiKey?: string): OpenAI {
  const apiKey = userApiKey || process.env.GROQ_API_KEY;
  if (!apiKey) {
    throw new Error(
      "Groq API key missing. Set GROQ_API_KEY in your .env.local file " +
        "or add it in the Settings panel. Get a free key at https://console.groq.com",
    );
  }
  return new OpenAI({ apiKey, baseURL: GROQ_BASE_URL });
}

function buildMessages(messages: ChatMessage[], context?: MedicalContext) {
  // Strip any existing system prompts from the incoming messages to prevent overrides
  const userMessages = messages.filter((m) => m.role !== "system");
  return [
    { role: "system" as const, content: resolveSystemPrompt(context) },
    ...userMessages,
  ];
}

// ─── Non-streaming ─────────────────────────────────────────────────────────

export async function chatGroq(args: {
  apiKey?: string;
  model: string;
  messages: ChatMessage[];
  context?: MedicalContext;
}): Promise<string> {
  const client = getClient(args.apiKey);
  const response = await client.chat.completions.create({
    model: args.model || GROQ_DEFAULT_MODEL,
    messages: buildMessages(args.messages, args.context) as any,
    temperature: 0.6,      // slightly lower → more consistent medical answers
    max_tokens: 1500,      // enough for structured 6-section medical response
    top_p: 0.9,
  });
  return response.choices[0]?.message?.content ?? "";
}

// ─── Streaming ─────────────────────────────────────────────────────────────

export async function* streamGroq(args: {
  apiKey?: string;
  model: string;
  messages: ChatMessage[];
  context?: MedicalContext;
}): AsyncGenerator<string, void, unknown> {
  const client = getClient(args.apiKey);
  const stream = await client.chat.completions.create({
    model: args.model || GROQ_DEFAULT_MODEL,
    messages: buildMessages(args.messages, args.context) as any,
    temperature: 0.6,
    max_tokens: 1500,
    top_p: 0.9,
    stream: true,
  });
  for await (const chunk of stream) {
    const content = chunk.choices[0]?.delta?.content;
    if (content) yield content;
  }
}
