import type { Preset, Provider } from "../types";

export type ResolvedPreset = {
  provider: Provider;
  model: string;
  fallbacks?: { provider: Provider; model: string }[];
  label: string;
};

const GROQ_PRIMARY = "llama-3.3-70b-versatile";
const GROQ_FAST    = "llama-3.1-8b-instant";

export const PRESETS: Record<Preset, ResolvedPreset> = {
  /**
   * RECOMMENDED — Groq + Llama 3.3 70B Versatile.
   * Fallback: Llama 3.1 8B Instant if 70B is rate-limited (HTTP 429).
   */
  "groq-best": {
    provider: "groq",
    model: GROQ_PRIMARY,
    fallbacks: [
      { provider: "groq", model: GROQ_FAST },
    ],
    label: "Llama 3.3 70B · Groq (recommended)",
  },

  /**
   * Ultra-fast — Groq + Llama 3.1 8B Instant (~800 tok/s).
   * Fallback: 70B versatile if 8B is unavailable.
   */
  "groq-fast": {
    provider: "groq",
    model: GROQ_FAST,
    fallbacks: [
      { provider: "groq", model: GROQ_PRIMARY },
    ],
    label: "Llama 3.1 8B Instant · Groq (fastest)",
  },
};

export function resolvePreset(preset: Preset): ResolvedPreset {
  const r = PRESETS[preset];
  if (!r) throw new Error(`Unknown preset: ${preset}`);
  return r;
}

/**
 * Default preset is always groq-best.
 * Can be overridden via DEFAULT_PRESET env var.
 */
export const DEFAULT_PRESET: Preset =
  (process.env.DEFAULT_PRESET as Preset) ?? "groq-best";
