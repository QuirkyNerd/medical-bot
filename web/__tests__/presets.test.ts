import { describe, it, expect } from "vitest";
import { PRESETS, resolvePreset, DEFAULT_PRESET } from "@/lib/providers/presets";

describe("presets", () => {
  it("exposes exactly the two Groq presets", () => {
    expect(Object.keys(PRESETS).sort()).toEqual(["groq-best", "groq-fast"].sort());
  });

  it("defaults to groq-best", () => {
    expect(DEFAULT_PRESET).toBe("groq-best");
  });

  it("groq-best uses Llama 3.3 70B", () => {
    const r = resolvePreset("groq-best");
    expect(r.provider).toBe("groq");
    expect(r.model).toContain("llama-3.3-70b");
    expect(r.fallbacks?.length ?? 0).toBeGreaterThanOrEqual(1);
  });

  it("groq-fast uses Llama 3.1 8B", () => {
    const r = resolvePreset("groq-fast");
    expect(r.provider).toBe("groq");
    expect(r.model).toContain("llama-3.1-8b");
  });

  it("throws on an unknown preset", () => {
    expect(() => resolvePreset("nope" as any)).toThrow();
  });
});
