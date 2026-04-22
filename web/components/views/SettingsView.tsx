"use client";

import { useState } from "react";
import {
  Globe,
  Type,
  Phone,
  ChevronDown,
  Cpu,
  Key,
  Activity,
  AlertTriangle,
  Mic,
  Sparkles,
  Zap,
  Sun,
  Moon,
} from "lucide-react";
import { Toggle } from "../chat/Toggle";
import type { Preset } from "@/lib/types";
import {
  t,
  LANGUAGE_NAMES,
  getCountryName,
  type SupportedLanguage,
} from "@/lib/i18n";
import type { TextSize } from "@/lib/hooks/useSettings";

interface SettingsViewProps {
  preset: Preset;
  setPreset: (p: Preset) => void;
  groqKey: string;
  setGroqKey: (key: string) => void;
  clearGroqKey: () => void;
  language: SupportedLanguage;
  setLanguage: (v: SupportedLanguage) => void;
  country: string;
  setCountry: (v: string) => void;
  voiceEnabled: boolean;
  setVoiceEnabled: (v: boolean) => void;
  readAloud: boolean;
  setReadAloud: (v: boolean) => void;
  textSize: TextSize;
  setTextSize: (v: TextSize) => void;
  simpleLanguage: boolean;
  setSimpleLanguage: (v: boolean) => void;
  darkMode: boolean;
  setDarkMode: (v: boolean) => void;
  emergencyNumber: string;
}

const COUNTRIES = [
  "US", "CA", "GB", "AU", "NZ", "IT", "DE", "FR", "ES", "PT", "NL", "PL",
  "IN", "CN", "JP", "KR", "BR", "MX", "AR", "CO", "ZA", "NG", "KE", "TZ",
  "EG", "MA", "TR", "RU", "SA", "AE", "PK", "BD", "VN", "TH", "PH", "ID", "MY",
];

export function SettingsView({
  preset,
  setPreset,
  groqKey,
  setGroqKey,
  clearGroqKey,
  language,
  setLanguage,
  country,
  setCountry,
  voiceEnabled,
  setVoiceEnabled,
  readAloud,
  setReadAloud,
  textSize,
  setTextSize,
  simpleLanguage,
  setSimpleLanguage,
  darkMode,
  setDarkMode,
  emergencyNumber,
}: SettingsViewProps) {
  const [isVerifying, setIsVerifying] = useState(false);
  const [verifyStatus, setVerifyStatus] = useState<{ success?: boolean; message?: string }>({});

  const handleVerify = async () => {
    if (!groqKey.trim()) { setVerifyStatus({ success: false, message: "Please enter an API key first" }); return; }
    setIsVerifying(true); setVerifyStatus({});
    try {
      const response = await fetch("/api/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider: "groq", apiKey: groqKey }),
      });
      const data = await response.json();
      setVerifyStatus({ success: data.success, message: data.success ? "Connection verified!" : data.error || "Connection failed" });
    } catch (e: any) {
      setVerifyStatus({ success: false, message: e?.message || "Network error" });
    } finally {
      setIsVerifying(false);
    }
  };

  return (
    <div className="flex-1 overflow-y-auto p-4 sm:p-8 pb-8 scroll-touch">
      <div className="max-w-2xl mx-auto animate-in fade-in slide-in-from-bottom-4 duration-500">
        <h2 className="text-2xl font-bold text-ink-base mb-6">{t("settings_title", language)}</h2>

        {/* ── GROQ AI ENGINE ─────────────────────────────────────────────── */}
        <Section icon={Cpu} title="Groq AI Engine">
          <div className="space-y-3">
            <PresetCard
              active={preset === "groq-best"}
              onClick={() => setPreset("groq-best")}
              icon={Sparkles}
              title="Llama 3.3 70B — Best quality"
              desc="Highest accuracy for medical reasoning. ~275 tok/s."
            />
            <PresetCard
              active={preset === "groq-fast"}
              onClick={() => setPreset("groq-fast")}
              icon={Zap}
              title="Llama 3.1 8B — Fastest"
              desc="Ultra-low latency. Ideal for slow connections or voice."
            />
          </div>

          <div className="mt-5 p-4 bg-surface-0 border border-line/60 rounded-xl">
            <div className="flex items-start gap-2 p-2.5 bg-brand-500/5 border border-brand-500/20 rounded-lg mb-3">
              <AlertTriangle size={13} className="text-brand-500 mt-0.5 flex-shrink-0" />
              <p className="text-[11px] text-ink-muted">
                <b>Groq API Key required.</b> Get yours free at{" "}
                <a href="https://console.groq.com" target="_blank" rel="noopener noreferrer" className="underline text-brand-600">
                  console.groq.com
                </a>
              </p>
            </div>
            <label className="text-xs font-semibold text-ink-muted uppercase tracking-wider mb-1.5 block">Groq API Key</label>
            <div className="relative">
              <Key size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-subtle" />
              <input
                type="password" value={groqKey}
                onChange={(e) => { setGroqKey(e.target.value); setVerifyStatus({}); }}
                placeholder="gsk_..."
                className="w-full bg-surface-1 border border-line/60 text-ink-base rounded-xl px-3 py-2.5 pl-8 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 transition-all"
              />
            </div>
            <div className="flex items-center justify-between mt-2.5">
              <div className="flex items-center gap-1.5">
                <div className={`w-2 h-2 rounded-full ${verifyStatus.success === true ? "bg-success-500" : verifyStatus.success === false ? "bg-danger-500" : "bg-ink-subtle/40"}`} />
                <span className="text-[11px] text-ink-muted">{verifyStatus.message || "Not verified"}</span>
              </div>
              <button
                onClick={handleVerify}
                disabled={isVerifying || !groqKey.trim()}
                className="text-xs font-bold text-brand-500 bg-brand-500/10 px-3 py-1.5 rounded-lg hover:bg-brand-500/20 border border-brand-500/20 flex items-center gap-1.5 disabled:opacity-50 transition-colors"
              >
                <Activity size={11} />
                {isVerifying ? "Verifying…" : "Verify"}
              </button>
            </div>
            {groqKey && (
              <button onClick={clearGroqKey} className="text-xs text-danger-500 hover:underline mt-2">
                Clear key
              </button>
            )}
          </div>
        </Section>

        {/* ── LANGUAGE & REGION ──────────────────────────────────────────── */}
        <Section icon={Globe} title={t("settings_language", language)}>
          <div className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-ink-muted uppercase tracking-wider">
                {t("settings_language", language)}
              </label>
              <div className="relative">
                <select
                  value={language}
                  onChange={(e) => setLanguage(e.target.value as SupportedLanguage)}
                  className="w-full appearance-none bg-surface-0 border border-line/60 text-ink-base rounded-xl px-4 py-3 pr-10 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 transition-all text-sm font-medium"
                >
                  {(Object.entries(LANGUAGE_NAMES) as [SupportedLanguage, string][]).map(([code, name]) => (
                    <option key={code} value={code}>{name}</option>
                  ))}
                </select>
                <ChevronDown size={15} className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-subtle pointer-events-none" />
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-ink-muted uppercase tracking-wider">
                {t("settings_country", language)}
              </label>
              <div className="relative">
                <select
                  value={country}
                  onChange={(e) => setCountry(e.target.value)}
                  className="w-full appearance-none bg-surface-0 border border-line/60 text-ink-base rounded-xl px-4 py-3 pr-10 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 transition-all text-sm font-medium"
                >
                  {COUNTRIES.map((code) => (
                    <option key={code} value={code}>{getCountryName(code)}</option>
                  ))}
                </select>
                <ChevronDown size={15} className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-subtle pointer-events-none" />
              </div>
            </div>
          </div>
        </Section>

        {/* ── APPEARANCE ─────────────────────────────────────────────────── */}
        <Section icon={Sun} title="Appearance">
          <div className="space-y-4">
            {/* Text size */}
            <div>
              <label className="text-xs font-semibold text-ink-muted uppercase tracking-wider mb-2 block">
                {t("settings_text_size", language)}
              </label>
              <div className="flex gap-2">
                {(["small", "medium", "large"] as TextSize[]).map((size) => (
                  <button
                    key={size}
                    onClick={() => setTextSize(size)}
                    className={`flex-1 py-2.5 rounded-xl text-sm font-semibold border-2 transition-all ${
                      textSize === size
                        ? "bg-brand-500/5 border-brand-500 text-brand-600"
                        : "bg-surface-0 border-line/60 text-ink-muted hover:border-brand-500/40"
                    }`}
                  >
                    {t(`settings_text_${size}` as any, language) || size}
                  </button>
                ))}
              </div>
            </div>

            <Toggle
              label={t("settings_simple_language", language)}
              description={t("settings_simple_language_desc", language)}
              enabled={simpleLanguage}
              setEnabled={setSimpleLanguage}
            />
          </div>
        </Section>

        {/* ── VOICE ──────────────────────────────────────────────────────── */}
        <Section icon={Mic} title={t("settings_voice", language)}>
          <Toggle label={t("settings_voice", language)} enabled={voiceEnabled} setEnabled={setVoiceEnabled} />
          <Toggle label={t("settings_read_aloud", language)} enabled={readAloud} setEnabled={setReadAloud} />
        </Section>

        {/* ── EMERGENCY ──────────────────────────────────────────────────── */}
        <Section icon={Phone} title={t("settings_emergency_number", language)}>
          <div className="flex items-center justify-between py-1">
            <span className="text-sm font-medium text-ink-base">{t("settings_emergency_number", language)}</span>
            <a href={`tel:${emergencyNumber}`} className="text-lg font-black text-danger-500 hover:underline">
              {emergencyNumber}
            </a>
          </div>
        </Section>


        <div className="h-8" />
      </div>
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

function Section({ icon: Icon, title, children }: { icon: any; title: string; children: React.ReactNode }) {
  return (
    <div className="bg-surface-1 rounded-2xl shadow-soft border border-line/40 overflow-hidden mb-4">
      <div className="p-4 bg-surface-2/40 border-b border-line/40 flex items-center gap-2">
        <Icon size={17} className="text-brand-500" />
        <h3 className="font-semibold text-ink-base">{title}</h3>
      </div>
      <div className="p-4">{children}</div>
    </div>
  );
}

function PresetCard({
  active,
  onClick,
  icon: Icon,
  title,
  desc,
}: {
  active: boolean;
  onClick: () => void;
  icon: any;
  title: string;
  desc: string;
}) {
  return (
    <button
      onClick={onClick}
      className={`w-full text-left p-4 rounded-xl border-2 transition-all ${
        active
          ? "bg-brand-500/5 border-brand-500"
          : "bg-surface-0 border-line/60 hover:border-brand-500/40"
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Icon size={15} className={active ? "text-brand-500" : "text-ink-muted"} />
          <span className={`font-semibold text-sm ${active ? "text-brand-600" : "text-ink-base"}`}>
            {title}
          </span>
        </div>
        {active && (
          <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-success-500/10 text-success-600">
            ACTIVE
          </span>
        )}
      </div>
      <p className="text-xs text-ink-muted mt-1">{desc}</p>
    </button>
  );
}

function ThemeBtn({
  active,
  icon: Icon,
  label,
  onClick,
}: {
  active: boolean;
  icon: any;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex-1 flex items-center justify-center gap-2 py-3 rounded-xl border-2 font-semibold text-sm transition-all ${
        active
          ? "bg-brand-500/5 border-brand-500 text-brand-600"
          : "bg-surface-0 border-line/60 text-ink-muted hover:border-brand-500/40"
      }`}
    >
      <Icon size={15} />
      {label}
    </button>
  );
}
