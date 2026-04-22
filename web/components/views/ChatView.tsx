"use client";

import { useMemo, useRef, useEffect, useState } from "react";
import { AlertTriangle, Phone, X, Stethoscope } from "lucide-react";
import { MessageBubble } from "../chat/MessageBubble";
import { HeroInput } from "../chat/HeroInput";
import { TypingIndicator } from "../chat/TypingIndicator";
import { TrustBar } from "../chat/TrustBar";
import type { ChatMessage } from "@/lib/hooks/useChat";
import { t, detectEmergencyKeywords, type SupportedLanguage } from "@/lib/i18n";

interface ChatViewProps {
  messages: ChatMessage[];
  isTyping: boolean;
  onSendMessage: (content: string, file?: File | null) => void;
  language?: SupportedLanguage;
  emergencyNumber?: string;
  voiceEnabled?: boolean;
  readAloud?: boolean;
  onNavigateEmergency?: () => void;
  onNewChat?: () => void;
}

export function ChatView({
  messages,
  isTyping,
  onSendMessage,
  language = "en",
  emergencyNumber = "108",
  voiceEnabled = true,
  readAloud = false,
  onNavigateEmergency,
  onNewChat,
}: ChatViewProps) {
  const [isListening, setIsListening] = useState(false);
  const [showEmergencyBanner, setShowEmergencyBanner] = useState(false);
  const chatEndRef = useRef<HTMLDivElement | null>(null);
  const recognitionRef = useRef<any>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  // Red-flag auto-detection on latest user message.
  useEffect(() => {
    if (messages.length === 0) return;
    const last = messages[messages.length - 1];
    if (last.role === "user" && detectEmergencyKeywords(last.content, language)) {
      setShowEmergencyBanner(true);
    }
  }, [messages, language]);

  // Read aloud the latest AI message.
  useEffect(() => {
    if (!readAloud || messages.length === 0) return;
    const last = messages[messages.length - 1];
    if (
      last.role === "ai" &&
      !isTyping &&
      typeof speechSynthesis !== "undefined"
    ) {
      const u = new SpeechSynthesisUtterance(last.content);
      u.lang = language;
      speechSynthesis.speak(u);
    }
  }, [messages, isTyping, readAloud, language]);

  const startVoice = () => {
    if (typeof window === "undefined") return;
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) return;
    const recognition = new SpeechRecognition();
    recognition.lang = language;
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.onresult = (event: any) => {
      const transcript = event.results[0][0].transcript;
      onSendMessage(transcript);
      setIsListening(false);
    };
    recognition.onerror = () => setIsListening(false);
    recognition.onend = () => setIsListening(false);
    recognitionRef.current = recognition;
    recognition.start();
    setIsListening(true);
  };

  const stopVoice = () => {
    recognitionRef.current?.stop();
    setIsListening(false);
  };

  // More than just the initial AI greeting = has real messages
  const hasMessages = messages.length > 1;

  // Suggestion chips — shown only on fresh/empty chat
  const suggestions = useMemo(() => {
    if (hasMessages) return [];
    return [
      t("ask_example_1", language),
      t("ask_example_2", language),
      t("ask_example_3", language),
      t("ask_example_4", language),
    ].filter(Boolean);
  }, [hasMessages, language]);

  return (
    // Outer wrapper: flex column that fills remaining height
    <div className="flex flex-col flex-1 min-h-0 overflow-hidden">
      {/* Red-flag emergency banner */}
      {showEmergencyBanner && (
        <div className="relative z-10 bg-danger-500 text-white p-4 flex items-center gap-3 animate-fade-up shadow-danger-glow flex-shrink-0">
          <AlertTriangle size={24} className="flex-shrink-0" />
          <div className="flex-1">
            <p className="font-bold text-base">
              {t("emergency_may_be", language)}
            </p>
            <p className="text-sm text-white/85">
              {t("emergency_call_now", language)}
            </p>
          </div>
          <a
            href={`tel:${emergencyNumber}`}
            className="px-5 py-2.5 bg-white text-danger-600 rounded-xl font-bold text-sm flex items-center gap-2 flex-shrink-0 hover:bg-white/90 transition-colors"
          >
            <Phone size={16} />
            {t("emergency_call", language)} {emergencyNumber}
          </a>
          <button
            onClick={() => setShowEmergencyBanner(false)}
            className="text-white/75 hover:text-white p-1"
            aria-label="Dismiss"
          >
            <X size={18} />
          </button>
        </div>
      )}

      {/* Scrollable conversation area */}
      <div className="flex-1 overflow-y-auto scroll-smooth scroll-touch">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 py-6">
          {/* Hero prompt on empty chat */}
          {!hasMessages && (
            <div className="text-center mb-8 animate-fade-up">
              <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-brand-gradient shadow-glow mb-4">
                <Stethoscope size={24} className="text-white" />
              </div>
              <h2 className="text-2xl font-bold text-ink-base tracking-tight mb-2">
                {t("ask_hero_title", language)}
              </h2>
              <p className="text-ink-muted leading-relaxed max-w-md mx-auto">
                {t("ask_hero_subtitle", language)}
              </p>
              <div className="mt-5">
                <TrustBar language={language} />
              </div>
            </div>
          )}

          {messages.map((msg, i) => (
            <MessageBubble
              key={msg.id}
              message={msg}
              showSourceChip={msg.role === "ai" && i <= 1}
            />
          ))}

          {isTyping && <TypingIndicator label={t("ai_analyzing", language)} />}

          <div ref={chatEndRef} className="h-4" />
        </div>
      </div>

      {/* Voice listening pill */}
      {isListening && (
        <div className="px-4 sm:px-6 pb-2 flex-shrink-0">
          <div className="max-w-3xl mx-auto">
            <div className="flex items-center justify-center gap-2 py-2 rounded-full bg-brand-500/10 border border-brand-500/30 text-brand-600 dark:text-brand-400 text-sm font-medium animate-pulse">
              {t("ask_tap_speak", language)}…
              <button onClick={stopVoice} className="ml-2 opacity-70 hover:opacity-100">
                <X size={14} />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Composer — sticky above keyboard, clear spacing from bottom */}
      <div className="flex-shrink-0 px-4 sm:px-6 pt-3 pb-5 bg-gradient-to-t from-surface-0 via-surface-0/95 to-transparent">
        <div className="max-w-3xl mx-auto">
          <HeroInput
            language={language}
            onSend={onSendMessage}
            onStartVoice={startVoice}
            onStopVoice={stopVoice}
            isListening={isListening}
            voiceEnabled={voiceEnabled}
            suggestions={suggestions}
            autoFocus
          />
        </div>
      </div>
    </div>
  );
}
