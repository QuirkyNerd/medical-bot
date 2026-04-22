"use client";

import {
  Home,
  MessageCircle,
  AlertTriangle,
  BookOpen,
  Settings,
  Heart,
  Calendar,
  Activity,
  FileText,
  Clock,
  MapPin,
} from "lucide-react";
import { NavItem } from "./NavItem";
import { t, type SupportedLanguage } from "@/lib/i18n";

export type NavView =
  | "home"
  | "chat"
  | "emergency"
  | "topics"
  | "records"
  | "vitals"
  | "health-dashboard"
  | "schedule"
  | "history"
  | "settings"
  | "nearby";

interface SidebarProps {
  activeNav: NavView;
  setActiveNav: (nav: string) => void;
  language?: SupportedLanguage;
  isAuthenticated?: boolean;
  username?: string;
  onLogout?: () => void;
}

export function Sidebar({ activeNav, setActiveNav, language = "en" }: SidebarProps) {
  const navTo = (view: string) => setActiveNav(view);

  return (
    <aside className="hidden md:flex flex-col z-20 bg-surface-1/80 backdrop-blur-xl border-r border-line/50 w-60 p-0">
      <div className="py-4 px-5 mb-2 border-b border-line/40">
        <h1 className="text-[18px] font-semibold text-ink-base">Medical Chatbot</h1>
      </div>
      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto space-y-0.5 scrollbar-thin px-4 pb-4">
        <NavItem icon={Home} label={t("nav_home", language)} active={activeNav === "home"} onClick={() => navTo("home")} />
        <NavItem icon={MessageCircle} label={t("nav_ask", language)} active={activeNav === "chat"} onClick={() => navTo("chat")} />

        <SectionLabel>{t("nav_health_tracker", language)}</SectionLabel>
        <NavItem icon={Heart} label={t("nav_dashboard", language)} active={activeNav === "health-dashboard"} onClick={() => navTo("health-dashboard")} />
        <NavItem icon={Calendar} label={t("nav_schedule", language)} active={activeNav === "schedule"} onClick={() => navTo("schedule")} />
        <NavItem icon={Activity} label={t("nav_vitals", language)} active={activeNav === "vitals"} onClick={() => navTo("vitals")} />
        <NavItem icon={FileText} label={t("nav_records", language)} active={activeNav === "records"} onClick={() => navTo("records")} />

        <SectionLabel>{t("nav_tools", language)}</SectionLabel>
        <NavItem icon={AlertTriangle} label={t("nav_emergency", language)} active={activeNav === "emergency"} onClick={() => navTo("emergency")} urgent />
        <NavItem icon={MapPin} label={t("nearby_title", language) || "Nearby"} active={activeNav === "nearby"} onClick={() => navTo("nearby")} />
        <NavItem icon={BookOpen} label={t("nav_topics", language)} active={activeNav === "topics"} onClick={() => navTo("topics")} />
        <NavItem icon={Clock} label={t("nav_history", language)} active={activeNav === "history"} onClick={() => navTo("history")} />

        <SectionLabel>Preferences</SectionLabel>
        <NavItem icon={Settings} label={t("nav_settings", language)} active={activeNav === "settings"} onClick={() => navTo("settings")} />
      </nav>
    </aside>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="mt-4 mb-1.5 px-4">
      <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-ink-subtle">
        {children}
      </span>
    </div>
  );
}
