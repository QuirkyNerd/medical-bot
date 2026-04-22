"use client";

import { useState, useCallback, useEffect } from "react";
import { Sidebar } from "./chat/Sidebar";
import { AppDrawer } from "./chat/AppDrawer";
import { WelcomeScreen } from "./WelcomeScreen";
import { LoginPage } from "./auth/LoginPage";

import { HomeView } from "./views/HomeView";
import { TopicsView } from "./views/TopicsView";
import { SettingsView } from "./views/SettingsView";
import { ChatView } from "./views/ChatView";
import { EmergencyView } from "./views/EmergencyView";
import { VitalsView } from "./views/VitalsView";
import { RecordsView } from "./views/RecordsView";
import { ScheduleView } from "./views/ScheduleView";
import { HealthDashboard } from "./views/HealthDashboard";
import { NearbyView } from "./views/NearbyView";
import { HistoryView } from "./views/HistoryView";
import { UserMenu } from "./auth/UserMenu";
import { Sun, Moon, PlusCircle } from "lucide-react";

import { useChat } from "@/lib/hooks/useChat";
import { useSettings } from "@/lib/hooks/useSettings";
import { useHealthStore } from "@/lib/hooks/useHealthStore";
import { useGeoDetect } from "@/lib/hooks/useGeoDetect";
import { useAuth } from "@/lib/hooks/useAuth";
import { type SupportedLanguage } from "@/lib/i18n";

export type NavItemKeys =
  | "home"
  | "chat"
  | "emergency"
  | "vitals"
  | "records"
  | "schedule"
  | "health-dashboard"
  | "history"
  | "nearby"
  | "topics"
  | "settings";

export default function MedOSApp() {
  const [activeNav, setActiveNav] = useState<NavItemKeys>("home");
  const [drawerOpen, setDrawerOpen] = useState(false);

  const auth = useAuth();
  const settings = useSettings();
  const { messages, isTyping, sendMessage, chats, createNewChat, loadChat, deleteChat } = useChat(auth.token);
  const health = useHealthStore(auth.token);

  const onGeo = useCallback(
    (g: { country: string; language: SupportedLanguage; emergencyNumber: string }) => {
      settings.applyGeo(g);
    },
    [settings],
  );
  useGeoDetect({ skip: !settings.isLoaded || settings.explicitLanguage, onResult: onGeo });

  useEffect(() => {
    const root = document.documentElement;
    root.classList.remove("text-small", "text-medium", "text-large", "dark");
    if (settings.darkMode) root.classList.add("dark");
    if (settings.textSize) root.classList.add(`text-${settings.textSize}`);
  }, [settings.darkMode, settings.textSize]);

  const handleSendMessage = (content: string, file?: File | null) => {
    sendMessage(content, { 
      file, 
      forceNewChat: activeNav === "home" || activeNav === "topics" 
    });
    if (activeNav !== "chat") setActiveNav("chat");
  };

  const handleStartVoice = () => setActiveNav("chat");

  const handleWelcomeComplete = (lang: SupportedLanguage, country: string) => {
    settings.setLanguageExplicit(lang);
    settings.setCountryExplicit(country);
    settings.setWelcomeCompleted(true);
  };

  const handleNavigate = (nav: string) => {
    setActiveNav(nav as NavItemKeys);
    setDrawerOpen(false);
  };

  const handleNewChat = () => {
    createNewChat();
    setActiveNav("chat");
  };

  if (auth.loading || !settings.isLoaded) {
    return (
      <div className="h-screen w-full flex items-center justify-center bg-surface-0">
        <div className="w-10 h-10 border-4 border-brand-500/30 border-t-brand-500 rounded-full animate-spin" />
      </div>
    );
  }

  if (!auth.isAuthenticated) {
    return <LoginPage auth={auth} language={settings.language} darkMode={settings.darkMode} />;
  }

  if (!settings.welcomeCompleted) {
    return (
      <WelcomeScreen
        detectedLanguage={settings.language}
        detectedCountry={settings.country}
        onComplete={handleWelcomeComplete}
      />
    );
  }

  const renderContent = () => {
    switch (activeNav) {
      case "home":
        return (
          <HomeView
            language={settings.language}
            country={settings.country}
            emergencyNumber={settings.emergencyNumber}
            onNavigate={handleNavigate}
            onSendMessage={handleSendMessage}
            onStartVoice={handleStartVoice}
          />
        );
      case "emergency":
        return <EmergencyView language={settings.language} emergencyNumber={settings.emergencyNumber} />;
      case "topics":
        return (
          <TopicsView
            language={settings.language}
            onSelectTopic={(topic) => handleSendMessage(`Tell me about ${topic}`)}
          />
        );
      case "settings":
        return (
          <SettingsView
            preset={settings.preset}
            setPreset={settings.setPreset}
            groqKey={settings.groqKey}
            setGroqKey={settings.setGroqKey}
            clearGroqKey={settings.clearGroqKey}
            language={settings.language}
            setLanguage={settings.setLanguageExplicit}
            country={settings.country}
            setCountry={settings.setCountryExplicit}
            voiceEnabled={settings.voiceEnabled}
            setVoiceEnabled={settings.setVoiceEnabled}
            readAloud={settings.readAloud}
            setReadAloud={settings.setReadAloud}
            textSize={settings.textSize}
            setTextSize={settings.setTextSize}
            simpleLanguage={settings.simpleLanguage}
            setSimpleLanguage={settings.setSimpleLanguage}
            darkMode={settings.darkMode}
            setDarkMode={settings.setDarkMode}
            emergencyNumber={settings.emergencyNumber}
          />
        );
      case "schedule":
        return (
          <ScheduleView
            medications={health.medications}
            medicationLogs={health.medicationLogs}
            appointments={health.appointments}
            dbSchedules={health.dbSchedules}
            onAddDbSchedule={health.addDbSchedule}
            onUpdateDbScheduleStatus={health.updateDbScheduleStatus}
            onMarkMedTaken={health.markMedTaken}
            isMedTaken={health.isMedTaken}
            onEditAppointment={health.editAppointment}
            onNavigate={handleNavigate}
            language={settings.language}
          />
        );
      case "health-dashboard":
        return (
          <HealthDashboard
            medications={health.medications}
            medicationLogs={health.medicationLogs}
            appointments={health.appointments}
            vitals={health.vitals}
            records={health.records}
            dbSchedules={health.dbSchedules}
            onUpdateDbScheduleStatus={health.updateDbScheduleStatus}
            onNavigate={handleNavigate}
            onMarkMedTaken={health.markMedTaken}
            isMedTaken={health.isMedTaken}
            getMedStreak={health.getMedStreak}
            onExport={health.downloadAll}
            language={settings.language}
          />
        );
      case "vitals":
        return (
          <VitalsView
            vitals={health.vitals}
            onAdd={health.addVital}
            onDelete={health.deleteVital}
            language={settings.language}
          />
        );
      case "records":
        return (
          <RecordsView
            records={health.records}
            onAdd={health.addRecord}
            onEdit={health.editRecord}
            onDelete={health.deleteRecord}
            onExport={health.downloadAll}
            language={settings.language}
          />
        );
      case "nearby":
        return <NearbyView language={settings.language} />;
      case "history":
        return (
          <HistoryView
            history={chats.map((c) => ({
              id: c.id,
              date: c.updatedAt,
              topic: "Chat",
              preview:
                c.messages.filter((m) => m.role === "user")[0]?.content ||
                "New conversation",
              messageCount: c.messages.length,
            }))}
            onDelete={deleteChat}
            onClearAll={() => alert("Clear all coming soon")}
            onReplay={(topic, id) => {
              if (id) {
                loadChat(id);
                handleNavigate("chat");
              } else {
                handleSendMessage(topic);
              }
            }}
            language={settings.language}
          />
        );
      case "chat":
      default:
        return (
          <ChatView
            messages={messages}
            isTyping={isTyping}
            onSendMessage={handleSendMessage}
            language={settings.language}
            emergencyNumber={settings.emergencyNumber}
            voiceEnabled={settings.voiceEnabled}
            readAloud={settings.readAloud}
            onNewChat={handleNewChat}
          />
        );
    }
  };

  const isChat = activeNav === "chat";

  return (
    <div className="flex h-[100dvh] w-full overflow-hidden bg-surface-0 text-ink-base font-sans">
      {/* Desktop Sidebar */}
      <Sidebar
        activeNav={activeNav as any}
        setActiveNav={(nav: string) => setActiveNav(nav as NavItemKeys)}
        language={settings.language}
        isAuthenticated={auth.isAuthenticated}
        username={auth.user?.displayName || auth.user?.email}
        onLogout={auth.logout}
      />

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-w-0 relative h-full overflow-hidden">

        {/* ── Unified top header bar ─────────────────────────────────────── */}
        <header className="flex-shrink-0 flex items-center justify-between h-14 px-4 sm:px-5 bg-surface-0/90 backdrop-blur-sm border-b border-line/40 z-30">
          {/* Left: hamburger (mobile) + title */}
          <div className="flex items-center gap-3">
            {/* Mobile menu button */}
            <button
              onClick={() => setDrawerOpen(true)}
              className="md:hidden p-2 -ml-1 rounded-xl text-ink-subtle hover:bg-surface-2"
              aria-label="Open menu"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <line x1="3" y1="6" x2="21" y2="6" />
                <line x1="3" y1="12" x2="21" y2="12" />
                <line x1="3" y1="18" x2="21" y2="18" />
              </svg>
            </button>
            <h1 className="font-bold text-base text-ink-base capitalize tracking-tight md:hidden">
              {activeNav === "home"
                ? "Home"
                : activeNav === "chat"
                  ? "Ask AI"
                  : activeNav === "health-dashboard"
                    ? "Dashboard"
                    : activeNav.replace(/-/g, " ")}
            </h1>
          </div>

          {/* Right: actions */}
          <div className="flex items-center gap-2">
            {/* New Chat — always in header */}
            <button
              onClick={handleNewChat}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-brand-500/10 hover:bg-brand-500/20 text-brand-600 dark:text-brand-400 font-semibold text-xs transition-colors border border-brand-500/20"
              title="Start new conversation"
            >
              <PlusCircle size={13} />
              <span className="hidden sm:inline">New Chat</span>
            </button>

            {/* Theme toggle */}
            <button
              onClick={() => settings.setDarkMode(!settings.darkMode)}
              className="p-2 rounded-xl text-ink-subtle hover:bg-surface-2 transition-colors"
              title="Toggle theme"
            >
              {settings.darkMode ? <Moon size={17} /> : <Sun size={17} />}
            </button>

            {/* User avatar + dropdown */}
            <UserMenu
              username={auth.user?.displayName || auth.user?.email || ""}
              onLogout={auth.logout}
              onSettings={() => setActiveNav("settings")}
            />
          </div>
        </header>

        {/* Page content */}
        <div className="flex-1 min-h-0 overflow-hidden flex flex-col">
          {renderContent()}
        </div>
      </main>

      {/* Mobile Drawer */}
      <AppDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        activeKey={activeNav}
        onNavigate={handleNavigate}
        isAuthenticated={auth.isAuthenticated}
        username={auth.user?.displayName || auth.user?.email}
        onLogout={auth.logout}
        language={settings.language}
      />
    </div>
  );
}
