"use client";

import { useState, useCallback, useEffect } from "react";
import { apiRequest } from "../api-client";

export interface ChatMessage {
  id: string;
  role: "user" | "ai";
  content: string;
  timestamp: string;
  metadata?: any;
}

export interface ChatSummary {
  id: string;
  title: string;
  updatedAt: string;
  messages: ChatMessage[];
}

export function useChat(authToken?: string | null) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chats, setChats] = useState<ChatSummary[]>([]);
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [isTyping, setIsTyping] = useState(false);

  // Load chat list
  const loadChatList = useCallback(async () => {
    if (!authToken) return;
    try {
      const data = await apiRequest("/api/conversations", { token: authToken });
      setChats(data.conversations || []);
    } catch (err) {
      console.error("Failed to load chats", err);
    }
  }, [authToken]);

  useEffect(() => {
    loadChatList();
  }, [loadChatList]);

  // Create new chat
  const createNewChat = useCallback(() => {
    setMessages([{
      id: "initial",
      role: "ai",
      content: "Hello! I am your Medical AI assistant. How can I help you today?",
      timestamp: new Date().toISOString()
    }]);
    setActiveChatId(null);
  }, []);

  // Load specific chat
  const loadChat = useCallback(async (id: string) => {
    if (!authToken) return;
    try {
      const data = await apiRequest(`/api/conversations/${id}`, { token: authToken });
      const formattedMessages = data.messages.map((m: any, index: number) => ({
        id: `${id}-${index}`,
        role: m.role === "assistant" ? "ai" : "user",
        content: m.content,
        timestamp: m.timestamp || new Date().toISOString(),
        metadata: m.metadata
      }));
      setMessages(formattedMessages);
      setActiveChatId(id);
    } catch (err) {
      console.error("Failed to load chat", err);
    }
  }, [authToken]);

  // Delete chat
  const deleteChat = useCallback(async (id: string) => {
    if (!authToken) return;
    try {
      await apiRequest(`/api/conversations/${id}`, {
        method: "DELETE",
        token: authToken
      });
      if (activeChatId === id) createNewChat();
      loadChatList();
    } catch (err) {
      console.error("Failed to delete chat", err);
    }
  }, [authToken, activeChatId, createNewChat, loadChatList]);

  // Send message
  const sendMessage = useCallback(async (content: string, options?: { file?: File | null, forceNewChat?: boolean }) => {
    if (!content.trim() && !options?.file) return;

    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      role: "user",
      content,
      timestamp: new Date().toISOString()
    };

    setMessages(prev => [...prev, userMsg]);
    setIsTyping(true);

    try {
      // 1. Get AI response from agent
      const response = await apiRequest("/api/agent/query", {
        method: "POST",
        token: authToken,
        json: {
          query: content,
          top_k: 6
        }
      });

      const aiMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: "ai",
        content: response.answer,
        timestamp: new Date().toISOString(),
        metadata: {
          sources: response.sources,
          confidence: response.confidence_level,
          badge: response.badge_label
        }
      };

      setMessages(prev => [...prev, aiMsg]);

      // 2. Persist conversation if authenticated
      if (authToken) {
        const conversationData = {
          id: options?.forceNewChat ? null : activeChatId,
          messages: [...messages, userMsg, aiMsg].map(m => ({
            role: m.role === "ai" ? "assistant" : "user",
            content: m.content,
            metadata: m.metadata
          }))
        };

        const saveRes = await apiRequest("/api/conversations", {
          method: "POST",
          token: authToken,
          json: conversationData
        });

        if (saveRes.id) {
          setActiveChatId(saveRes.id);
          loadChatList();
        }
      }
    } catch (err: any) {
      console.error("Chat error", err);
      setMessages(prev => [...prev, {
        id: "error",
        role: "ai",
        content: `Sorry, I encountered an error: ${err.message}. Please try again later.`,
        timestamp: new Date().toISOString()
      }]);
    } finally {
      setIsTyping(false);
    }
  }, [authToken, activeChatId, messages, loadChatList]);

  // Initial greeting if empty
  useEffect(() => {
    if (messages.length === 0) {
      createNewChat();
    }
  }, [messages.length, createNewChat]);

  return {
    messages,
    chats,
    isTyping,
    sendMessage,
    createNewChat,
    loadChat,
    deleteChat,
    activeChatId
  };
}