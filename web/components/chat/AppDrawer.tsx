"use client";

import { useEffect } from "react";
import {
  X,
  MessageCircle,
  Clock,
  MapPin,
  Heart,
  Activity,
  FileText,
  Calendar,
  Settings,
  AlertTriangle,
  BookOpen,
  LogOut,
  Home,
} from "lucide-react";
import { t, type SupportedLanguage } from "@/lib/i18n";

interface AppDrawerProps {
  open: boolean;
  onClose: () => void;
  activeKey: string;
  onNavigate: (key: string) => void;
  isAuthenticated?: boolean;
  username?: string;
  onLogout?: () => void;
  language: SupportedLanguage;
}

export function AppDrawer({
  open,
  onClose,
  activeKey,
  onNavigate,
  username,
  onLogout,
  language,
}: AppDrawerProps) {
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  useEffect(() => {
    if (open) document.body.style.overflow = "hidden";
    else document.body.style.overflow = "";
    return () => { document.body.style.overflow = ""; };
  }, [open]);

  const nav = (key: string) => { onNavigate(key); onClose(); };
  const displayName = (username || "").split("@")[0] || "Account";

  return (
    <div
      className={`md:hidden fixed inset-0 z-50 transition-all duration-300 ${
        open ? "pointer-events-auto" : "pointer-events-none"
      }`}
      aria-hidden={!open}
    >
      {/* Backdrop */}
      <div
        className={`absolute inset-0 bg-black/40 backdrop-blur-sm transition-opacity duration-300 ${
          open ? "opacity-100" : "opacity-0"
        }`}
        onClick={onClose}
      />

      {/* Drawer panel */}
      <aside
        className={`absolute left-0 top-0 h-full w-[82%] max-w-[320px] bg-surface-1 border-r border-line/40 shadow-card flex flex-col transition-transform duration-300 ease-out ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 pt-5 pb-3 safe-area-top border-b border-line/40">
          <span className="font-bold text-base text-ink-base">Medical Chatbot</span>
          <button
            onClick={onClose}
            className="w-9 h-9 rounded-xl flex items-center justify-center text-ink-subtle hover:text-ink-base hover:bg-surface-2 transition-all"
            aria-label="Close menu"
          >
            <X size={17} />
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto px-3 py-2 scroll-touch">
          <DrawerSection title={t("drawer_section_main", language)}>
            <DrawerItem icon={Home} label={t("nav_home", language)} active={activeKey === "home"} onClick={() => nav("home")} />
            <DrawerItem icon={MessageCircle} label={t("nav_ask", language)} active={activeKey === "chat"} onClick={() => nav("chat")} />
            <DrawerItem icon={Clock} label={t("nav_history", language)} active={activeKey === "history"} onClick={() => nav("history")} />
          </DrawerSection>

          <DrawerSection title={t("nav_health_tracker", language)}>
            <DrawerItem icon={Heart} label={t("nav_dashboard", language)} active={activeKey === "health-dashboard"} onClick={() => nav("health-dashboard")} />
            <DrawerItem icon={Calendar} label={t("nav_schedule", language)} active={activeKey === "schedule"} onClick={() => nav("schedule")} />
            <DrawerItem icon={Activity} label={t("nav_vitals", language)} active={activeKey === "vitals"} onClick={() => nav("vitals")} />
            <DrawerItem icon={FileText} label={t("nav_records", language)} active={activeKey === "records"} onClick={() => nav("records")} />
          </DrawerSection>

          <DrawerSection title={t("drawer_section_tools", language)}>
            <DrawerItem icon={AlertTriangle} label={t("nav_emergency", language)} active={activeKey === "emergency"} onClick={() => nav("emergency")} urgent />
            <DrawerItem icon={MapPin} label={t("drawer_nearby", language) || "Nearby"} active={activeKey === "nearby"} onClick={() => nav("nearby")} />
            <DrawerItem icon={BookOpen} label={t("nav_topics", language)} active={activeKey === "topics"} onClick={() => nav("topics")} />
            <DrawerItem icon={Settings} label={t("nav_settings", language)} active={activeKey === "settings"} onClick={() => nav("settings")} />
          </DrawerSection>
        </nav>

        {/* Footer */}
        <div className="px-4 py-3 border-t border-line/40 safe-area-bottom">
          <p className="text-xs text-ink-muted font-medium mb-2 truncate">{displayName}</p>
          {onLogout && (
            <button
              onClick={() => { onLogout(); onClose(); }}
              className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-sm font-semibold text-danger-500 hover:bg-danger-500/10 transition-colors"
            >
              <LogOut size={15} /> Sign out
            </button>
          )}
          <p className="text-[10px] text-ink-subtle leading-snug px-1 mt-2">
            {t("badge_not_doctor", language)}
          </p>
        </div>
      </aside>
    </div>
  );
}

function DrawerSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="py-2">
      <div className="px-3 pb-1.5 pt-1 text-[10px] font-bold uppercase tracking-[0.14em] text-ink-subtle">
        {title}
      </div>
      <div className="space-y-0.5">{children}</div>
    </div>
  );
}

function DrawerItem({
  icon: Icon,
  label,
  active,
  onClick,
  urgent,
}: {
  icon: any;
  label: string;
  active: boolean;
  onClick: () => void;
  urgent?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      className={`w-full h-11 rounded-xl px-3 flex items-center gap-3 text-left transition-all active:scale-[0.98] ${
        active
          ? urgent
            ? "bg-danger-500/10 text-danger-500 font-semibold"
            : "bg-brand-500/10 text-brand-600 font-semibold"
          : urgent
            ? "text-danger-500/80 hover:bg-danger-500/5"
            : "text-ink-muted hover:bg-surface-2 hover:text-ink-base"
      }`}
    >
      <Icon size={17} strokeWidth={active ? 2.25 : 1.75} className="flex-shrink-0" />
      <span className="text-sm truncate">{label}</span>
    </button>
  );
}
