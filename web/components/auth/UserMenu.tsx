"use client";

import { useState, useRef, useEffect } from "react";
import { ChevronDown, Settings, LogOut, User2 } from "lucide-react";

interface UserMenuProps {
  username: string;
  onLogout: () => void;
  onSettings: () => void;
}

export function UserMenu({ username, onLogout, onSettings }: UserMenuProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const displayName = username?.split("@")[0] || "Account";
  const initial = displayName[0]?.toUpperCase() || "U";

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 px-2.5 py-1.5 rounded-xl hover:bg-surface-2 transition-colors group"
        aria-label="User menu"
      >
        <div className="w-7 h-7 rounded-full bg-brand-gradient flex items-center justify-center text-white text-xs font-bold flex-shrink-0 shadow-sm">
          {initial}
        </div>
        <span className="hidden sm:block text-sm font-semibold text-ink-base max-w-[120px] truncate">
          {displayName}
        </span>
        <ChevronDown
          size={14}
          className={`text-ink-subtle transition-transform duration-200 ${open ? "rotate-180" : ""}`}
        />
      </button>

      {open && (
        <>
          {/* Backdrop */}
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />

          {/* Dropdown */}
          <div className="absolute right-0 top-full mt-2 w-52 bg-surface-1 border border-line/60 rounded-2xl shadow-card z-50 overflow-hidden animate-in fade-in slide-in-from-top-2 duration-150">
            {/* User info header */}
            <div className="px-4 py-3 border-b border-line/40">
              <div className="flex items-center gap-2.5">
                <div className="w-9 h-9 rounded-full bg-brand-gradient flex items-center justify-center text-white text-sm font-bold flex-shrink-0">
                  {initial}
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-bold text-ink-base truncate">{displayName}</p>
                  <p className="text-[11px] text-ink-subtle truncate">{username}</p>
                </div>
              </div>
            </div>

            {/* Menu items */}
            <div className="p-1.5 space-y-0.5">
              <MenuBtn icon={LogOut} label="Sign out" onClick={() => { setOpen(false); onLogout(); }} danger />
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function MenuBtn({
  icon: Icon,
  label,
  onClick,
  danger,
}: {
  icon: any;
  label: string;
  onClick: () => void;
  danger?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-sm font-medium transition-colors text-left ${
        danger
          ? "text-danger-500 hover:bg-danger-500/10"
          : "text-ink-base hover:bg-surface-2"
      }`}
    >
      <Icon size={15} className={danger ? "text-danger-500" : "text-ink-subtle"} />
      {label}
    </button>
  );
}
