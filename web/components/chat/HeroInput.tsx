"use client";

import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { Send, Mic, MicOff, Sparkles, Paperclip, FileImage, FileText, X } from "lucide-react";
import { t, type SupportedLanguage } from "@/lib/i18n";

interface HeroInputProps {
  language: SupportedLanguage;
  onSend: (value: string, file?: File | null) => void;
  onStartVoice?: () => void;
  onStopVoice?: () => void;
  voiceEnabled?: boolean;
  isListening?: boolean;
  /** Dynamic suggestion chips rendered under the input (empty = hide). */
  suggestions?: string[];
  /** Variant — the home hero uses a larger, more prominent size. */
  size?: "default" | "hero";
  /** Autofocus on mount (chat view). */
  autoFocus?: boolean;
}

/**
 * The single most important element of the app: the input.
 * - Large, generous rounded container with a soft brand glow on focus.
 * - Rotating empathetic placeholders so the field never feels empty.
 * - Multi-line textarea that auto-grows up to 5 rows.
 * - Inline primary send button + optional voice mic.
 * - Suggestion chips appear below for zero-friction entry.
 */
export function HeroInput({
  language,
  onSend,
  onStartVoice,
  onStopVoice,
  voiceEnabled = true,
  isListening = false,
  suggestions = [],
  size = "default",
  autoFocus = false,
}: HeroInputProps) {
  const [value, setValue] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const taRef = useRef<HTMLTextAreaElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Rotating empathetic placeholders.
  const rotating = useMemo(
    () => [
      t("ask_placeholder_rotate_1", language),
      t("ask_placeholder_rotate_2", language),
      t("ask_placeholder_rotate_3", language),
      t("ask_placeholder_rotate_4", language),
      t("ask_placeholder_rotate_5", language),
    ],
    [language],
  );
  const [rotIdx, setRotIdx] = useState(0);
  useEffect(() => {
    if (value) return; // freeze rotation while the user is typing
    const id = setInterval(() => setRotIdx((i) => (i + 1) % rotating.length), 3200);
    return () => clearInterval(id);
  }, [value, rotating.length]);

  // Auto-grow textarea.
  useEffect(() => {
    const el = taRef.current;
    if (!el) return;
    el.style.height = "0px";
    const max = size === "hero" ? 180 : 160;
    el.style.height = `${Math.min(el.scrollHeight, max)}px`;
  }, [value, size]);

  useEffect(() => {
    if (autoFocus) taRef.current?.focus();
  }, [autoFocus]);

  const handleKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  const isHero = size === "hero";

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFileError(null);
    const selected = e.target.files?.[0];
    if (!selected) return;

    if (selected.size > 10 * 1024 * 1024) {
      setFileError("File exceeds 10MB limit.");
      return;
    }

    const allowedTypes = ["image/jpeg", "image/png", "image/webp", "application/pdf"];
    if (!allowedTypes.includes(selected.type)) {
      setFileError("Invalid file type. Please upload a JPG, PNG, or PDF.");
      return;
    }

    setFile(selected);
  };

  const removeFile = () => {
    setFile(null);
    setFileError(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const submit = () => {
    const v = value.trim();
    if (!v && !file) return;
    onSend(v, file);
    setValue("");
    setFile(null);
    setFileError(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  return (
    <div className="w-full">
      {/* The glowing container */}
      <div
        className={`relative group rounded-[28px] bg-surface-1 border border-line/70 shadow-card transition-all focus-within:border-brand-500/60 focus-within:shadow-glow ${
          isHero ? "p-2.5" : "p-2"
        }`}
      >
        {/* Soft gradient halo behind the card */}
        <div
          aria-hidden
          className="pointer-events-none absolute -inset-px -z-10 rounded-[28px] bg-brand-gradient opacity-0 group-focus-within:opacity-40 blur-xl transition-opacity"
        />

        {/* File Preview Bar */}
        {file && (
          <div className="flex items-center gap-3 bg-surface-2/50 p-2 rounded-t-2xl border-b border-line/40 mx-2 mt-2">
            <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-surface-1 border border-line/60">
              {file.type.startsWith("image/") ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={URL.createObjectURL(file)} alt="preview" className="w-full h-full object-cover rounded-lg" />
              ) : (
                <FileText size={20} className="text-brand-500" />
              )}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold text-ink-base truncate">{file.name}</p>
              <p className="text-[10px] text-ink-muted">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
            </div>
            <button onClick={removeFile} className="p-1.5 rounded-full hover:bg-surface-3 text-ink-muted hover:text-danger-500 transition-colors">
              <X size={14} />
            </button>
          </div>
        )}

        {/* File Error Bar */}
        {fileError && (
          <div className="mx-2 mt-2 p-2 rounded-lg bg-danger-50 text-danger-600 dark:bg-danger-900/20 text-xs flex justify-between items-center">
            <span>{fileError}</span>
            <button onClick={() => setFileError(null)} className="opacity-70 hover:opacity-100">
              <X size={12} />
            </button>
          </div>
        )}

        <div className="flex items-end gap-2 p-2">
          <div className="flex-1 relative">
            <textarea
              ref={taRef}
              rows={1}
              value={value}
              onChange={(e) => setValue(e.target.value)}
              onKeyDown={handleKey}
              placeholder={rotating[rotIdx]}
              className={`w-full resize-none bg-transparent text-ink-base placeholder:text-ink-subtle outline-none leading-relaxed px-4 py-3 ${
                isHero ? "text-lg" : "text-base"
              }`}
              aria-label={t("ask_placeholder", language)}
            />
          </div>

          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            accept="image/jpeg,image/png,image/webp,application/pdf"
            className="hidden"
          />

          {/* Attachment */}
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            aria-label="Attach file"
            className={`flex-shrink-0 rounded-full flex items-center justify-center transition-all w-11 h-11 bg-surface-2 text-ink-muted hover:text-brand-600 hover:bg-brand-50 dark:hover:bg-brand-900/30`}
          >
            <Paperclip size={isHero ? 18 : 16} />
          </button>

          {/* Voice */}
          {voiceEnabled && (
            <button
              type="button"
              onClick={isListening ? onStopVoice : onStartVoice}
              aria-label={t("ask_tap_speak", language)}
              className={`flex-shrink-0 rounded-full flex items-center justify-center transition-all w-11 h-11 ${
                isListening
                  ? "bg-danger-500 text-white animate-pulse shadow-danger-glow"
                  : "bg-surface-2 text-ink-muted hover:text-brand-600 hover:bg-brand-50 dark:hover:bg-brand-900/30"
              }`}
            >
              {isListening ? <MicOff size={isHero ? 18 : 16} /> : <Mic size={isHero ? 18 : 16} />}
            </button>
          )}

          {/* Send — always present, brand gradient when there's text */}
          <button
            type="button"
            onClick={submit}
            disabled={!value.trim() && !file}
            aria-label="Send"
            className={`flex-shrink-0 rounded-full flex items-center justify-center transition-all ${
              isHero ? "w-12 h-12" : "w-10 h-10"
            } ${
              value.trim() || file
                ? "bg-brand-gradient text-white shadow-glow hover:brightness-110"
                : "bg-surface-2 text-ink-subtle cursor-not-allowed"
            }`}
          >
            <Send size={isHero ? 20 : 16} strokeWidth={2.5} />
          </button>
        </div>
      </div>

      {/* Suggestion chips — dynamic, click to send */}
      {suggestions.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2 justify-center">
          <span className="inline-flex items-center gap-1 text-[11px] font-semibold uppercase tracking-wider text-ink-muted">
            <Sparkles size={12} className="text-accent-500" />
            {t("ask_suggestions", language)}
          </span>
          {suggestions.map((s, i) => (
            <button
              key={`${s}-${i}`}
              type="button"
              onClick={() => onSend(s)}
              className="px-3.5 py-1.5 rounded-full bg-surface-1 border border-line/70 text-sm text-ink-muted hover:text-brand-600 hover:border-brand-500/50 hover:bg-brand-50/60 dark:hover:bg-brand-900/20 transition-colors"
            >
              {s}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
