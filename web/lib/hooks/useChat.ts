"use client";

import { useState, useCallback, useEffect, useMemo } from "react";
import type { Provider, Preset } from "../types";
import { buildPatientContext, buildMedicineInventoryContext, buildContactsContext } from "../health-store";

export type ChatMessage = {
  id: number;
  role: "user" | "ai";
  content: string;
  timestamp: string;
  /** RAG retrieval confidence score (0–1). Present on text queries only. */
  confidence?: number;
  /** Human-readable confidence category (e.g. "High Confidence"). */
  confidence_label?: string;
  /** RAG sources returned by the backend pipeline. */
  sources?: Array<{
    text: string;
    source: string;
    page?: number;
    score: number;
  }>;
  /** Which pipeline type handled this message. */
  queryType?: "text" | "image" | "pdf";
  /** Model used for generation */
  model_used?: string;
};

export type SendOptions = {
  preset?: Preset;
  provider?: Provider;
  model?: string;
  apiKey?: string;
  context?: {
    country: string;
    language: string;
    emergencyNumber: string;
    units?: "metric" | "imperial";
  };
  file?: File | null;
  forceNewChat?: boolean;
};

const fileToBase64 = (file: File): Promise<string> => {
  return new Promise((resolve, reject) => {
    // Local extractors/OCR often fail on raw WEBP formats
    if (file.type === "image/webp") {
      const url = URL.createObjectURL(file);
      const img = new Image();
      img.onload = () => {
        const canvas = document.createElement("canvas");
        canvas.width = img.width;
        canvas.height = img.height;
        const ctx = canvas.getContext("2d");
        if (ctx) {
          ctx.drawImage(img, 0, 0);
          resolve(canvas.toDataURL("image/jpeg", 0.95)); // Normalize to JPEG
        } else {
          const reader = new FileReader();
          reader.readAsDataURL(file);
          reader.onload = () => resolve(reader.result as string);
        }
        URL.revokeObjectURL(url);
      };
      img.onerror = () => reject(new Error("Failed to process webp image"));
      img.src = url;
    } else {
      const reader = new FileReader();
      reader.readAsDataURL(file);
      reader.onload = () => resolve(reader.result as string);
      reader.onerror = (error) => reject(error);
    }
  });
};

export type ChatSession = {
  id: string;
  messages: ChatMessage[];
  updatedAt: string;
};

export function useChat(authToken?: string | null) {
  const [chats, setChats] = useState<ChatSession[]>([]);
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [isTyping, setIsTyping] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  // ── Load from backend ──────────────────────────────────────────────────────
  const loadChatFromServer = useCallback(async (id: string) => {
    if (!authToken) return;
    try {
      const res = await fetch(`/api/conversations/${id}`, {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (res.ok) {
        const data = await res.json();
        setChats((prev) =>
          prev.map((c) =>
            c.id === id ? { ...c, messages: data.messages } : c
          )
        );
      }
    } catch (e) {
      console.error("Failed to load chat", id, e);
    }
  }, [authToken]);

  const fetchChats = useCallback(async () => {
    if (!authToken) {
      setChats([]);
      setActiveChatId(null);
      return;
    }
    try {
      const res = await fetch("/api/conversations", {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (res.ok) {
        const data = await res.json();
        const mapped = data.conversations.map((c: any) => ({
          id: c.id,
          messages: [],
          updatedAt: c.updated_at,
          title: c.title,
        }));
        setChats(mapped);
        
        const savedId = sessionStorage.getItem("medos_active_chat_id");
        if (savedId && mapped.some((c: any) => c.id === savedId)) {
          setActiveChatId(savedId);
          loadChatFromServer(savedId);
        } else if (mapped.length > 0) {
          setActiveChatId(mapped[0].id);
          loadChatFromServer(mapped[0].id);
        }
      }
    } catch (e) {
      console.error("Failed to fetch chats", e);
    }
  }, [authToken, loadChatFromServer]);

  useEffect(() => {
    fetchChats();
  }, [fetchChats]);

  // Sync activeChatId to session so tab refreshes keep the same chat open
  useEffect(() => {
    if (activeChatId) {
      sessionStorage.setItem("medos_active_chat_id", activeChatId);
    } else {
      sessionStorage.removeItem("medos_active_chat_id");
    }
  }, [activeChatId]);

  // Server sync for upserting chats
  const syncChatToServer = useCallback(async (chatToSync: ChatSession) => {
    if (!authToken) return;
    try {
      await fetch("/api/conversations", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify({
          id: chatToSync.id,
          messages: chatToSync.messages.map((m) => ({
            role: m.role === "ai" ? "assistant" : "user",
            content: m.content,
            metadata: {
              confidence: m.confidence,
              confidence_label: m.confidence_label,
              sources: m.sources,
              queryType: m.queryType,
              model_used: m.model_used,
            },
          })),
        }),
      });
    } catch (e) {
      console.error("Failed to sync chat", e);
    }
  }, [authToken]);

  // ── Derived state ──────────────────────────────────────────────────────────
  const activeMessages = useMemo(() => {
    if (!activeChatId) return [];
    return chats.find((c) => c.id === activeChatId)?.messages || [];
  }, [chats, activeChatId]);

  // ── Helpers ────────────────────────────────────────────────────────────────
  const GREETING: ChatMessage = {
    id: Date.now(),
    role: "ai",
    content:
      "Hello! I'm your medical AI assistant. I'm here to help answer health questions and provide guidance. How can I assist you today?\n\n*Please note: I'm an AI and cannot replace professional medical advice. For emergencies, please call 108 or visit your nearest emergency room.*",
    timestamp: new Date().toISOString(),
  };

  const ensureActiveChat = (): string => {
    if (activeChatId && chats.some((c) => c.id === activeChatId)) return activeChatId;
    const newId = `chat_${Date.now()}`;
    const greeting = { ...GREETING, id: Date.now() };
    setChats((prev) => [
      { id: newId, messages: [greeting], updatedAt: new Date().toISOString() },
      ...prev,
    ]);
    setActiveChatId(newId);
    return newId;
  };

  const createNewChat = () => {
    const newId = `chat_${Date.now()}`;
    const greeting = { ...GREETING, id: Date.now() };
    setChats((prev) => [
      { id: newId, messages: [greeting], updatedAt: new Date().toISOString() },
      ...prev,
    ]);
    setActiveChatId(newId);
    return newId;
  };

  const loadChat = (id: string) => {
    if (chats.some((c) => c.id === id)) {
      setActiveChatId(id);
      loadChatFromServer(id);
    }
  };

  const deleteChat = (id: string) => {
    setChats((prev) => {
      const remaining = prev.filter((c) => c.id !== id);
      if (activeChatId === id) {
        const newActive = remaining.length > 0 ? remaining[0].id : null;
        setActiveChatId(newActive);
        if (newActive) loadChatFromServer(newActive);
      }
      return remaining;
    });
    if (authToken) {
      fetch(`/api/conversations/${id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${authToken}` },
      }).catch(console.error);
    }
  };

  // ── Core send logic ────────────────────────────────────────────────────────
  const sendMessage = useCallback(
    async (content: string, options: SendOptions = {}) => {
      let chatId = activeChatId;
      
      if (options.forceNewChat) {
        chatId = createNewChat();
      } else if (!chatId || !chats.some((c) => c.id === chatId)) {
        chatId = ensureActiveChat();
      }

      const timestamp = new Date().toISOString();
      let displayContent = content.trim();
      if (options.file) {
        displayContent = displayContent 
          ? `${displayContent}\n\n📎 [Attachment: ${options.file.name}]` 
          : `📎 [Attachment: ${options.file.name}]`;
      }

      const userMsg: ChatMessage = {
        id: Date.now(),
        role: "user",
        content: displayContent,
        timestamp,
      };

      // Append user message immediately for responsive UX
      setChats((prev) =>
        prev.map((c) =>
          c.id === chatId
            ? { ...c, messages: [...c.messages, userMsg], updatedAt: timestamp }
            : c
        )
      );

      setIsTyping(true);
      setError(null);

      try {
        const fullText = content.trim();

        let finalPayload: any;
        if (options.file) {
          const base64 = await fileToBase64(options.file);
          const isImage = options.file.type.startsWith("image/");
          const type = isImage ? "image" : "pdf";
          finalPayload = {
            type,
            [type]: base64,
            message: fullText,
          };
        } else {
          finalPayload = {
            type: "text",
            query: fullText,
          };
        }

        // Abort after 60 seconds
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 60_000);

        const res = await fetch("/api/medical-query", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          signal: controller.signal,
          body: JSON.stringify(finalPayload),
        });

        clearTimeout(timer);

        if (!res.ok) {
          let detail = `Server error (${res.status})`;
          try {
            const j = await res.json();
            detail = j.error ?? j.detail ?? detail;
          } catch {}
          throw new Error(detail);
        }

        const data = await res.json();

        if (!data.success) {
          throw new Error(data.error ?? "Unknown error from medical-query API");
        }

        const aiMsg: ChatMessage = {
          id: Date.now() + 1,
          role: "ai",
          content: (data.answer as string) || "No response received.",
          timestamp: new Date().toISOString(),
          confidence:
            typeof data.confidence === "number" ? data.confidence : undefined,
          confidence_label:
            typeof data.confidence_label === "string" ? data.confidence_label : undefined,
          sources:
            Array.isArray(data.sources) && data.sources.length > 0
              ? data.sources
              : undefined,
          queryType: ["text", "image", "pdf"].includes(data.type) ? data.type : "text",
          model_used: typeof data.model_used === "string" ? data.model_used : undefined,
        };

        const updatedChatState = (prev: ChatSession[]) =>
          prev.map((c) =>
            c.id === chatId
              ? { ...c, messages: [...c.messages, aiMsg], updatedAt: new Date().toISOString() }
              : c
          );
        setChats(updatedChatState);

        // Sync complete chat to server
        setTimeout(() => {
          setChats(currentChats => {
            const chatToSync = currentChats.find(c => c.id === chatId);
            if (chatToSync) syncChatToServer(chatToSync);
            return currentChats;
          });
        }, 0);
      } catch (err: any) {
        const isAbort = err.name === "AbortError";
        const isFetch = err.message === "Failed to fetch";

        const errorMsg = isAbort
          ? "The request timed out. Please try again."
          : isFetch
          ? "Unable to reach the server. Please check your connection and try again."
          : `Unable to fetch response: ${err.message}`;

        setError(err);

        const errAiMsg: ChatMessage = {
          id: Date.now(),
          role: "ai",
          content: `⚠️ ${errorMsg}`,
          timestamp: new Date().toISOString(),
        };

        setChats((prev) =>
          prev.map((c) =>
            c.id === chatId
              ? { ...c, messages: [...c.messages, errAiMsg], updatedAt: new Date().toISOString() }
              : c
          )
        );
      } finally {
        setIsTyping(false);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [activeChatId, chats, syncChatToServer]
  );

  return {
    messages: activeMessages,
    isTyping,
    error,
    sendMessage,
    chats,
    activeChatId,
    createNewChat,
    loadChat,
    deleteChat,
  };
}
