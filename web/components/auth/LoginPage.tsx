"use client";

import { useState } from "react";
import {
  Mail,
  Lock,
  User2,
  ArrowRight,
  ArrowLeft,
  AlertCircle,
  CheckCircle,
  KeyRound,
  ShieldCheck,
  Heart,
  Eye,
  EyeOff
} from "lucide-react";
import type { useAuth } from "@/lib/hooks/useAuth";
import { type SupportedLanguage } from "@/lib/i18n";

type AuthInstance = ReturnType<typeof useAuth>;
type AuthFlow = "login" | "register" | "verify" | "forgot" | "reset";

interface LoginPageProps {
  auth: AuthInstance;
  language: SupportedLanguage;
  darkMode: boolean;
}

export function LoginPage({ auth, darkMode }: LoginPageProps) {
  const [flow, setFlow] = useState<AuthFlow>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);

  const clear = () => { setError(""); setSuccess(""); };

  const handleLogin = async () => {
    if (!email || !password) { setError("Email and password required"); return; }
    setLoading(true); clear();
    const res = await auth.login(email, password);
    setLoading(false);
    if (!res.ok) setError(res.error || "Invalid email or password. Please try again.");
  };

  const handleRegister = async () => {
    if (!email || !password) { setError("Email and password required"); return; }
    if (password.length < 6) { setError("Password must be at least 6 characters"); return; }
    setLoading(true); clear();
    const res = await auth.register(email, password, { displayName: displayName || undefined });
    setLoading(false);
    if (!res.ok) { setError(res.error || "Registration failed"); return; }
    if (res.needsVerification) {
      setSuccess("Account created! Check your email for a verification code.");
      setFlow("verify");
    }
  };

  const handleVerify = async () => {
    if (!code || code.length !== 6) { setError("Enter the 6-digit code from your email"); return; }
    setLoading(true); clear();
    const res = await auth.verifyEmail(code);
    setLoading(false);
    if (res.ok) setSuccess("Email verified! You're all set.");
    else setError(res.error || "Invalid code");
  };

  const handleForgot = async () => {
    if (!email) { setError("Enter your email address"); return; }
    setLoading(true); clear();
    const res = await auth.forgotPassword(email);
    setLoading(false);
    setSuccess(res.message || "If that email is registered, a reset code has been sent.");
    setFlow("reset");
  };

  const handleReset = async () => {
    if (!code || !newPassword) { setError("Enter the code and your new password"); return; }
    setLoading(true); clear();
    const res = await auth.resetPassword(email, code, newPassword);
    setLoading(false);
    if (res.ok) {
      setSuccess("Password reset! You can now log in.");
      setFlow("login");
    } else {
      setError(res.error || "Reset failed");
    }
  };

  const titles: Record<AuthFlow, string> = {
    login: "",
    register: "Create your account",
    verify: "Verify your email",
    forgot: "Forgot password",
    reset: "Reset password",
  };

  const subtitles: Record<AuthFlow, string> = {
    login: "Sign in to your account",
    register: "Free forever.",
    verify: "Enter the 6-digit code we sent to your email",
    forgot: "We'll send a reset code to your email",
    reset: "Enter the code from your email and your new password",
  };

  return (
    <div className={`min-h-screen flex flex-col items-center justify-center p-4 bg-gradient-to-br from-brand-500/5 via-surface-0 to-accent-500/5 ${darkMode ? "dark" : ""}`}>
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 mx-auto mb-4 rounded-3xl bg-brand-gradient flex items-center justify-center shadow-glow">
            {flow === "verify" ? (
              <ShieldCheck size={28} className="text-white" />
            ) : flow === "forgot" || flow === "reset" ? (
              <KeyRound size={28} className="text-white" />
            ) : (
              <Heart size={28} className="text-white" />
            )}
          </div>
          <h1 className="text-3xl font-black text-ink-base tracking-tight mb-1">Medical chatbot</h1>
          <h2 className="text-lg font-bold text-ink-base mb-1">{titles[flow]}</h2>
          <p className="text-sm text-ink-muted">{subtitles[flow]}</p>
        </div>

        {/* Card */}
        <div className="bg-surface-1 border border-line/40 rounded-3xl shadow-card p-6 space-y-4">
          {/* Status */}
          {error && (
            <div className="flex items-center gap-2 text-sm text-danger-500 bg-danger-500/10 border border-danger-500/20 rounded-xl px-3 py-2.5">
              <AlertCircle size={14} className="flex-shrink-0" />
              {error}
            </div>
          )}
          {success && (
            <div className="flex items-center gap-2 text-sm text-success-600 bg-success-500/10 border border-success-500/20 rounded-xl px-3 py-2.5">
              <CheckCircle size={14} className="flex-shrink-0" />
              {success}
            </div>
          )}

          {/* LOGIN */}
          {flow === "login" && (
            <>
              <Field icon={Mail} type="email" value={email} onChange={setEmail} placeholder="your@email.com" label="Email" autoComplete="email" />
              <Field icon={Lock} type="password" value={password} onChange={setPassword} placeholder="Your password" label="Password" autoComplete="current-password" onEnter={handleLogin} />
              <PrimaryBtn loading={loading} onClick={handleLogin} label="Sign in" />
              <div className="flex items-center justify-between text-sm pt-1">
                <button onClick={() => { setFlow("register"); clear(); }} className="text-brand-500 hover:text-brand-600 font-semibold">
                  Create account
                </button>
                <button onClick={() => { setFlow("forgot"); clear(); }} className="text-ink-muted hover:text-ink-base font-medium">
                  Forgot password?
                </button>
              </div>
            </>
          )}

          {/* REGISTER */}
          {flow === "register" && (
            <>
              <Field icon={User2} type="text" value={displayName} onChange={setDisplayName} placeholder="Your name" label="Name (optional)" autoComplete="name" />
              <Field icon={Mail} type="email" value={email} onChange={setEmail} placeholder="your@email.com" label="Email" autoComplete="email" />
              <Field icon={Lock} type="password" value={password} onChange={setPassword} placeholder="Min. 6 characters" label="Password" autoComplete="new-password" onEnter={handleRegister} />
              <PrimaryBtn loading={loading} onClick={handleRegister} label="Create account" />
              <BackLink onClick={() => { setFlow("login"); clear(); }} label="Already have an account? Sign in" />
            </>
          )}

          {/* VERIFY */}
          {flow === "verify" && (
            <>
              <div>
                <label className="text-xs font-semibold text-ink-muted uppercase tracking-wider mb-1.5 block">Verification code</label>
                <input
                  type="text" inputMode="numeric" maxLength={6} value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                  placeholder="000000" onKeyDown={(e) => e.key === "Enter" && handleVerify()}
                  className="w-full bg-surface-2 border border-line/60 text-ink-base rounded-xl px-4 py-4 text-center text-2xl font-black tracking-[0.5em] focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
                />
              </div>
              <PrimaryBtn loading={loading} onClick={handleVerify} label="Verify email" />
              <div className="text-center">
                <button onClick={auth.resendVerification} className="text-sm text-brand-500 hover:text-brand-600 font-semibold">Resend code</button>
              </div>
              <BackLink onClick={() => { setFlow("login"); clear(); }} label="Back to sign in" />
            </>
          )}

          {/* FORGOT */}
          {flow === "forgot" && (
            <>
              <Field icon={Mail} type="email" value={email} onChange={setEmail} placeholder="your@email.com" label="Email" autoComplete="email" onEnter={handleForgot} />
              <PrimaryBtn loading={loading} onClick={handleForgot} label="Send reset code" />
              <BackLink onClick={() => { setFlow("login"); clear(); }} label="Back to sign in" />
            </>
          )}

          {/* RESET */}
          {flow === "reset" && (
            <>
              <div>
                <label className="text-xs font-semibold text-ink-muted uppercase tracking-wider mb-1.5 block">Reset code</label>
                <input
                  type="text" inputMode="numeric" maxLength={6} value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                  placeholder="000000"
                  className="w-full bg-surface-2 border border-line/60 text-ink-base rounded-xl px-4 py-4 text-center text-2xl font-black tracking-[0.5em] focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
                />
              </div>
              <Field icon={Lock} type="password" value={newPassword} onChange={setNewPassword} placeholder="New password (min. 6)" label="New password" autoComplete="new-password" onEnter={handleReset} />
              <PrimaryBtn loading={loading} onClick={handleReset} label="Reset password" />
              <BackLink onClick={() => { setFlow("login"); clear(); }} label="Back to sign in" />
            </>
          )}
        </div>

        <p className="text-center text-[11px] text-ink-subtle mt-6 px-4">
        </p>
      </div>
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

function Field({ icon: Icon, type, value, onChange, placeholder, label, autoComplete, onEnter }: {
  icon: any; type: string; value: string; onChange: (v: string) => void;
  placeholder: string; label: string; autoComplete?: string; onEnter?: () => void;
}) {
  const [showPassword, setShowPassword] = useState(false);
  const isPassword = type === "password";
  const inputType = isPassword ? (showPassword ? "text" : "password") : type;

  return (
    <div>
      <label className="text-xs font-semibold text-ink-muted uppercase tracking-wider mb-1.5 block">{label}</label>
      <div className="relative">
        <Icon size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-subtle" />
        <input
          type={inputType} value={value} onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder} autoComplete={autoComplete}
          className="w-full bg-surface-2 border border-line/60 text-ink-base rounded-xl pl-9 pr-10 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500 transition-all"
          onKeyDown={(e) => e.key === "Enter" && onEnter?.()}
        />
        {isPassword && (
          <button
            type="button"
            onClick={() => setShowPassword(!showPassword)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-subtle hover:text-ink-base transition-colors"
          >
            {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
          </button>
        )}
      </div>
    </div>
  );
}

function PrimaryBtn({ loading, onClick, label }: { loading: boolean; onClick: () => void; label: string }) {
  return (
    <button onClick={onClick} disabled={loading}
      className="w-full py-3 bg-brand-gradient text-white rounded-xl font-bold text-sm shadow-glow hover:brightness-110 active:scale-[0.98] transition-all disabled:opacity-50 flex items-center justify-center gap-2"
    >
      {loading ? <span className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" /> : <>{label} <ArrowRight size={15} /></>}
    </button>
  );
}

function BackLink({ onClick, label }: { onClick: () => void; label: string }) {
  return (
    <div className="text-center">
      <button onClick={onClick} className="text-sm text-brand-500 hover:text-brand-600 font-semibold inline-flex items-center gap-1">
        <ArrowLeft size={13} /> {label}
      </button>
    </div>
  );
}
