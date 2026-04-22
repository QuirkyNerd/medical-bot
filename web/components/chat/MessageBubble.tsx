"use client";

import { useState } from "react";
import { Stethoscope, User2, ShieldCheck, BookOpen, ChevronDown, ChevronRight, Activity, Database, Cpu, FileText, Download, Copy } from "lucide-react";
import type { ChatMessage } from "@/lib/hooks/useChat";

interface MessageBubbleProps {
  message: ChatMessage;
  showSourceChip?: boolean;
}


export function MessageBubble({ message, showSourceChip }: MessageBubbleProps) {
  const isUser = message.role === "user";

  if (isUser) {
    return (
      <div className="flex justify-end mb-6 animate-fade-up">
        <div className="max-w-[85%] flex items-start gap-2">
          <div className="order-2 flex-shrink-0 w-9 h-9 rounded-full bg-surface-2 flex items-center justify-center text-ink-muted">
            <User2 size={16} />
          </div>
          <div className="order-1">
            <div className="rounded-2xl rounded-tr-sm px-4 py-3 bg-brand-gradient text-white shadow-soft leading-relaxed text-[15px]">
              <p className="whitespace-pre-wrap">{message.content}</p>
            </div>
            <div className="mt-1 text-[11px] text-ink-subtle text-right">
              {message.timestamp}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start mb-6 animate-fade-up">
      <div className="max-w-[88%] flex items-start gap-3">
        <div className="flex-shrink-0 w-9 h-9 rounded-full bg-brand-gradient flex items-center justify-center text-white shadow-soft">
          <Stethoscope size={16} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1.5">
            <span className="text-xs font-bold text-ink-base tracking-tight">
              Medical chatbot
            </span>
            {showSourceChip && (
              <span className="inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider text-accent-600 dark:text-accent-400 bg-accent-500/10 border border-accent-500/20 px-2 py-0.5 rounded-full">
                <ShieldCheck size={10} />
                WHO · CDC · NHS
              </span>
            )}
          </div>
          <div className="rounded-2xl rounded-tl-sm border border-line/60 bg-surface-1 shadow-soft px-4 py-3.5 text-[15px] leading-relaxed text-ink-base">
            <MarkdownContent content={message.content} />
          </div>
          <div className="mt-1 text-[11px] text-ink-subtle">
            {message.timestamp}
          </div>

          {/* ── Confidence badge ─────────────────────────────── */}
          {typeof message.confidence === "number" && (
            <div className="mt-1.5 flex items-center gap-1">
              <span
                className={`inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full border ${
                  message.confidence >= 0.65
                    ? "bg-emerald-500/10 border-emerald-500/25 text-emerald-600 dark:text-emerald-400"
                    : message.confidence >= 0.4
                    ? "bg-amber-500/10 border-amber-500/25 text-amber-600 dark:text-amber-400"
                    : "bg-surface-2 border-line/40 text-ink-subtle"
                }`}
              >
                RAG: {message.confidence_label || `${Math.round(message.confidence * 100)}% confidence`}
              </span>
            </div>
          )}

          {/* ── Explainability Panel ─────────────────────────────── */}
          {message.role === "ai" && message.queryType === "text" && (
            <ExplainabilityPanel message={message} />
          )}

          {/* ── Action Strip (PDF/Export) ──────────────────────── */}
          {message.role === "ai" && (
            <ActionStrip message={message} />
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * MarkdownContent — lightweight markdown renderer for medical AI output.
 *
 * Supports: headers (#), bold (**), italic (*), bullet lists (- / *),
 * numbered lists (1.), inline code (`), code blocks (```), links [text](url),
 * and horizontal rules (---).
 *
 * No external dependencies — pure React + regex.
 */
function MarkdownContent({ content }: { content: string }) {
  if (!content) return null;

  const blocks = parseBlocks(content);

  return (
    <div className="space-y-2">
      {blocks.map((block, i) => (
        <BlockRenderer key={i} block={block} />
      ))}
    </div>
  );
}

type Block =
  | { type: "heading"; level: number; text: string }
  | { type: "paragraph"; text: string }
  | { type: "list"; ordered: boolean; items: string[] }
  | { type: "code"; language: string; code: string }
  | { type: "hr" };

function parseBlocks(text: string): Block[] {
  const lines = text.split("\n");
  const blocks: Block[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    // Code block
    if (line.trimStart().startsWith("```")) {
      const lang = line.trimStart().slice(3).trim();
      const codeLines: string[] = [];
      i++;
      while (i < lines.length && !lines[i].trimStart().startsWith("```")) {
        codeLines.push(lines[i]);
        i++;
      }
      blocks.push({ type: "code", language: lang, code: codeLines.join("\n") });
      i++;
      continue;
    }

    // Horizontal rule
    if (/^(-{3,}|_{3,}|\*{3,})\s*$/.test(line.trim())) {
      blocks.push({ type: "hr" });
      i++;
      continue;
    }

    // Heading
    const headingMatch = line.match(/^(#{1,4})\s+(.+)$/);
    if (headingMatch) {
      blocks.push({ type: "heading", level: headingMatch[1].length, text: headingMatch[2] });
      i++;
      continue;
    }

    // Bold heading pattern: **Heading**
    const boldHeadingMatch = line.match(/^\*\*([^*]+)\*\*\s*:?\s*$/);
    if (boldHeadingMatch) {
      blocks.push({ type: "heading", level: 3, text: boldHeadingMatch[1] });
      i++;
      continue;
    }

    // List (unordered: - or *, ordered: 1.)
    if (/^\s*[-*]\s+/.test(line) || /^\s*\d+\.\s+/.test(line)) {
      const ordered = /^\s*\d+\./.test(line);
      const items: string[] = [];
      while (i < lines.length && (/^\s*[-*]\s+/.test(lines[i]) || /^\s*\d+\.\s+/.test(lines[i]))) {
        items.push(lines[i].replace(/^\s*[-*]\s+/, "").replace(/^\s*\d+\.\s+/, ""));
        i++;
      }
      blocks.push({ type: "list", ordered, items });
      continue;
    }

    // Empty line
    if (line.trim() === "") {
      i++;
      continue;
    }

    // Paragraph — collect consecutive non-empty lines
    const paraLines: string[] = [];
    while (i < lines.length && lines[i].trim() !== "" && !lines[i].trimStart().startsWith("```") && !lines[i].match(/^#{1,4}\s/) && !lines[i].match(/^\*\*[^*]+\*\*\s*:?\s*$/) && !/^\s*[-*]\s+/.test(lines[i]) && !/^\s*\d+\.\s+/.test(lines[i]) && !/^(-{3,}|_{3,}|\*{3,})\s*$/.test(lines[i].trim())) {
      paraLines.push(lines[i]);
      i++;
    }
    if (paraLines.length > 0) {
      blocks.push({ type: "paragraph", text: paraLines.join("\n") });
    }
  }

  return blocks;
}

function BlockRenderer({ block }: { block: Block }) {
  switch (block.type) {
    case "heading":
      return (
        <div className="answer-section">
          <h4 className={`font-bold text-brand-600 dark:text-brand-400 mb-1 ${
            block.level <= 2 ? "text-[15px]" : "text-[13px] uppercase tracking-wider"
          }`}>
            {renderInline(block.text)}
          </h4>
        </div>
      );

    case "paragraph":
      return (
        <p className="whitespace-pre-wrap text-ink-base/95 leading-relaxed">
          {renderInline(block.text)}
        </p>
      );

    case "list":
      const ListTag = block.ordered ? "ol" : "ul";
      return (
        <ListTag className={`space-y-1 pl-1 ${block.ordered ? "list-decimal list-inside" : ""}`}>
          {block.items.map((item, i) => (
            <li key={i} className="text-ink-base/95 leading-relaxed flex items-start gap-2">
              {!block.ordered && <span className="text-brand-500 mt-1.5 text-xs flex-shrink-0">•</span>}
              <span>{renderInline(item)}</span>
            </li>
          ))}
        </ListTag>
      );

    case "code":
      return (
        <pre className="bg-surface-2 border border-line/40 rounded-xl p-3 overflow-x-auto text-[13px] font-mono text-ink-base/90 leading-relaxed">
          <code>{block.code}</code>
        </pre>
      );

    case "hr":
      return <hr className="border-line/40 my-2" />;

    default:
      return null;
  }
}

/**
 * Render inline markdown: **bold**, *italic*, `code`, [link](url)
 */
function renderInline(text: string): React.ReactNode {
  if (!text) return null;

  // Split on inline patterns and render
  const parts: React.ReactNode[] = [];
  let remaining = text;
  let key = 0;

  while (remaining.length > 0) {
    // Bold: **text**
    const boldMatch = remaining.match(/\*\*(.+?)\*\*/);
    // Italic: *text* (but not **)
    const italicMatch = remaining.match(/(?<!\*)\*([^*]+?)\*(?!\*)/);
    // Inline code: `code`
    const codeMatch = remaining.match(/`([^`]+?)`/);
    // Link: [text](url)
    const linkMatch = remaining.match(/\[([^\]]+?)\]\(([^)]+?)\)/);

    // Find the earliest match
    const matches = [
      boldMatch ? { match: boldMatch, type: "bold" as const } : null,
      italicMatch ? { match: italicMatch, type: "italic" as const } : null,
      codeMatch ? { match: codeMatch, type: "code" as const } : null,
      linkMatch ? { match: linkMatch, type: "link" as const } : null,
    ].filter(Boolean).sort((a, b) => a!.match.index! - b!.match.index!);

    if (matches.length === 0) {
      parts.push(remaining);
      break;
    }

    const first = matches[0]!;
    const idx = first.match.index!;

    // Text before match
    if (idx > 0) {
      parts.push(remaining.slice(0, idx));
    }

    // Render the matched element
    switch (first.type) {
      case "bold":
        parts.push(<strong key={key++} className="font-bold">{first.match[1]}</strong>);
        remaining = remaining.slice(idx + first.match[0].length);
        break;
      case "italic":
        parts.push(<em key={key++} className="italic">{first.match[1]}</em>);
        remaining = remaining.slice(idx + first.match[0].length);
        break;
      case "code":
        parts.push(
          <code key={key++} className="bg-surface-2 border border-line/40 rounded px-1.5 py-0.5 text-[13px] font-mono text-ink-base/90">
            {first.match[1]}
          </code>
        );
        remaining = remaining.slice(idx + first.match[0].length);
        break;
      case "link":
        parts.push(
          <a key={key++} href={first.match[2]} target="_blank" rel="noopener noreferrer"
            className="text-brand-500 hover:text-brand-600 underline underline-offset-2">
            {first.match[1]}
          </a>
        );
        remaining = remaining.slice(idx + first.match[0].length);
        break;
    }
  }

  return <>{parts}</>;
}

// ---------------------------------------------------------------------------
// Explainability Components
// ---------------------------------------------------------------------------

function ExplainabilityPanel({ message }: { message: ChatMessage }) {
  const [isOpen, setIsOpen] = useState(false);
  
  const hasRag = (message.sources && message.sources.length > 0) || message.confidence !== undefined;

  return (
    <div className="mt-4 overflow-hidden rounded-xl border border-line/60 bg-surface-0 shadow-sm transition-all duration-200">
      <button 
        onClick={() => setIsOpen(!isOpen)}
        className="flex w-full items-center justify-between bg-surface-1 px-3 py-2.5 text-left hover:bg-surface-2 transition-colors focus:outline-none"
      >
        <div className="flex items-center gap-2">
          <Activity size={14} className="text-brand-500" />
          <span className="text-[11px] font-bold text-ink-base uppercase tracking-wider">How this answer was generated</span>
        </div>
        {isOpen ? <ChevronDown size={14} className="text-ink-subtle" /> : <ChevronRight size={14} className="text-ink-subtle" />}
      </button>

      {isOpen && (
        <div className="p-3 border-t border-line/60 space-y-4 animate-fade-in">
          
          {/* Pipeline Map */}
          <div>
            <h4 className="text-[10px] font-bold text-ink-subtle uppercase tracking-wider mb-2">Generation Pipeline</h4>
            <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-ink-muted">
              <span className="flex items-center gap-1 bg-surface-2 px-2 py-1 rounded-md"><User2 size={10}/> Query</span>
              <span className="text-line">→</span>
              <span className={`flex items-center gap-1 px-2 py-1 rounded-md ${hasRag ? 'bg-brand-50 text-brand-600 dark:bg-brand-900/30 font-medium' : 'bg-surface-2 opacity-50'}`}>
                <Database size={10}/> Retrieval
              </span>
              <span className="text-line">→</span>
              <span className={`flex items-center gap-1 px-2 py-1 rounded-md ${hasRag ? 'bg-brand-50 text-brand-600 dark:bg-brand-900/30 font-medium' : 'bg-surface-2 opacity-50'}`}>
                <Activity size={10}/> Ranking
              </span>
              <span className="text-line">→</span>
              <span className="flex items-center gap-1 bg-surface-2 px-2 py-1 rounded-md"><Cpu size={10}/> LLM</span>
              <span className="text-line">→</span>
              <span className="flex items-center gap-1 bg-surface-2 px-2 py-1 rounded-md"><FileText size={10}/> Response</span>
            </div>
          </div>

          {/* Model Info */}
          <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] bg-surface-1 p-2 rounded-lg border border-line/40">
            <div className="flex items-center gap-2">
              <Cpu size={12} className="text-ink-subtle" />
              <span className="text-ink-base font-medium">Model:</span>
              <span className="text-ink-muted truncate max-w-[120px] sm:max-w-none">{message.model_used || "llama-3.3-70b-versatile"}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className={`w-1.5 h-1.5 rounded-full ${hasRag ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]" : "bg-ink-muted"}`} />
              <span className="text-ink-muted font-medium">{hasRag ? "RAG Enhanced" : "Base Knowledge"}</span>
            </div>
          </div>

          {/* Evidence/Sources */}
          {hasRag && message.sources && message.sources.length > 0 && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <h4 className="text-[10px] font-bold text-ink-subtle uppercase tracking-wider">Evidence Sources</h4>
              </div>
              <div className="space-y-1.5">
                {message.sources.map((src, i) => (
                  <EvidenceItem key={i} src={src} index={i} />
                ))}
              </div>
            </div>
          )}

        </div>
      )}
    </div>
  );
}

function EvidenceItem({ src, index }: { src: NonNullable<ChatMessage["sources"]>[number], index: number }) {
  const [expanded, setExpanded] = useState(false);
  
  const relevance = Math.round(src.score * 100);
  const snippet = src.text.length > 400 && !expanded ? src.text.slice(0, 400) + "..." : src.text;

  return (
    <div className="bg-surface-0 border border-line/60 overflow-hidden rounded-lg text-[11px] text-ink-base hover:border-brand-500/30 transition-colors">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-2 relative">
        <div className="flex items-center gap-2">
          <BookOpen size={12} className="text-brand-500 flex-shrink-0" />
          <span className="font-semibold text-brand-600 dark:text-brand-400 leading-snug">
            {src.source} {src.page ? `(Page ${src.page})` : ""}
          </span>
          <span className="hidden sm:inline-block uppercase text-[9px] font-bold tracking-wider text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-1.5 py-0.5 rounded ml-1">
            {relevance}% match
          </span>
        </div>
        <button 
           onClick={() => setExpanded(!expanded)}
           className="text-[10px] font-semibold text-ink-subtle hover:text-brand-500 transition-colors flex items-center gap-1 self-start sm:self-auto bg-surface-1 px-2 py-1 rounded"
        >
          {expanded ? "Hide Evidence" : "View Evidence"}
          {expanded ? <ChevronDown size={10}/> : <ChevronRight size={10}/>}
        </button>
      </div>
      
      <div className="px-3 pb-3 pt-1 border-t border-line/20 bg-surface-1/50 animate-fade-in">
        <div className="flex items-center gap-2 mb-2 text-ink-muted text-[10px]">
          <span className="flex items-center gap-1"><FileText size={10}/> Document Snippet</span>
        </div>
        <div className="bg-surface-0 p-2.5 rounded shadow-inner text-[11px] font-mono text-ink-muted whitespace-pre-wrap leading-relaxed italic border-l-2 border-brand-400 relative">
          <span className="opacity-90">
            {snippet}
          </span>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Export & Action Tools
// ---------------------------------------------------------------------------

function ActionStrip({ message }: { message: ChatMessage }) {
  const [isExporting, setIsExporting] = useState(false);

  const handleDownload = async () => {
    setIsExporting(true);
    try {
      // @ts-ignore - Dynamically import html2pdf to prevent SSR issues
      const html2pdf = (await import("html2pdf.js")).default;
      
      const element = document.createElement("div");
      
      // Basic formatting to convert markdown block into primitive html
      let formattedHtmlContent = message.content
        .replace(/\n\n/g, '<br/><br/>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/### (.*?)\n/g, '<h3 style="color:#0f766e; margin-bottom:8px;">$1</h3>')
        .replace(/## (.*?)\n/g, '<h2 style="color:#0f766e; margin-bottom:8px; border-bottom: 1px solid #eee; padding-bottom: 4px;">$1</h2>')
        .replace(/\d+\.\s(.*?)\n/g, '<li style="margin-left: 16px;">$1</li>')
        .replace(/\-\s(.*?)\n/g, '<li style="margin-left: 16px;">$1</li>');

      element.innerHTML = `
        <div style="font-family: Arial, sans-serif; padding: 40px; color: #111827;">
          <h1 style="color: #0d9488; font-size: 24px; border-bottom: 2px solid #e5e7eb; padding-bottom: 16px; margin-bottom: 24px;">Medical AI Report</h1>
          <div style="margin-bottom: 24px;">
            <p><strong>Generated Date:</strong> ${new Date().toLocaleString()}</p>
            <p><strong>Model Pipeline:</strong> ${message.model_used || "Unified LLM"}</p>
            ${message.confidence_label ? `<p><strong>Retrieval Confidence:</strong> ${message.confidence_label}</p>` : ''}
          </div>
          
          <div style="background-color: #f3f4f6; padding: 16px; border-radius: 8px; margin-bottom: 32px;">
            <h3 style="margin-top: 0; color: #374151;">Assessment Overview</h3>
            <p style="margin-bottom: 0;">This document contains automated clinical insights generated by our AI system pipelines and should not replace primary care physicians.</p>
          </div>

          <h2 style="color: #1f2937; padding-bottom: 8px; border-bottom: 1px solid #e5e7eb;">Analysis Details</h2>
          <div style="line-height: 1.6; font-size: 14px; color: #374151; margin-bottom: 40px;">
            ${formattedHtmlContent}
          </div>

          ${message.sources && message.sources.length > 0 ? `
            <div style="page-break-before: always;"></div>
            <h2 style="color: #1f2937; padding-bottom: 8px; border-bottom: 1px solid #e5e7eb;">System Audit Log & Sources</h2>
            <ul style="font-size: 12px; color: #4b5563;">
              ${message.sources.map(src => `<li style="margin-bottom: 6px;">${src.source}${src.page ? ` (Page ${src.page})` : ''} - ${(src.score * 100).toFixed(1)}% match</li>`).join("")}
            </ul>
          ` : ''}

          <div style="margin-top: 60px; padding-top: 20px; border-top: 1px dashed #cbd5e1; font-size: 10px; color: #64748b; text-align: justify;">
            <strong>DISCLAIMER & LIABILITY LIMITATION:</strong> This AI-generated report is entirely for informational and educational purposes. It does not constitute formal medical diagnosis, treatment, or clinical advice. Consult a certified medical practitioner immediately regarding absolute medical decisions or emergency symptoms. The platform operators accept no liability.
          </div>
        </div>
      `;

      const opt = {
        margin:       0,
        filename:     `Medical_Report_${Date.now()}.pdf`,
        image:        { type: 'jpeg', quality: 0.98 },
        html2canvas:  { scale: 2 },
        jsPDF:        { unit: 'in', format: 'letter', orientation: 'portrait' }
      };

      await html2pdf().set(opt).from(element).save();
    } catch (e) {
      console.error(e);
    } finally {
      setIsExporting(false);
    }
  };

  const handleCopy = () => {
    let plainText = `MEDICAL AI REPORT\nGenerated: ${new Date().toLocaleString()}\n\n`;
    plainText += `${message.content}\n\n`;
    if (message.sources) {
      plainText += `SOURCES:\n${message.sources.map(s => `${s.source}${s.page ? ` (Page ${s.page})` : ''}`).join("\n")}\n\n`;
    }
    plainText += `DISCLAIMER: This system output is informational. Please consult a qualified healthcare professional.`;
    navigator.clipboard.writeText(plainText);
  }

  return (
    <div className="mt-3 flex flex-wrap items-center justify-end gap-2 border-t border-line/40 pt-3 animate-fade-in">
      <button onClick={handleCopy} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-2 hover:bg-surface-3 transition-colors outline-none focus-visible:ring-2 focus-visible:ring-brand-500 text-[10px] font-bold tracking-wider text-ink-muted uppercase shadow-sm">
        <Copy size={12} /> <span className="hidden sm:inline">Copy Text</span>
      </button>
      <button disabled={isExporting} onClick={handleDownload} className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-brand-50 text-brand-600 border border-brand-500/20 hover:bg-brand-100 hover:border-brand-500/40 dark:text-brand-400 dark:bg-brand-900/30 dark:hover:bg-brand-900/50 transition-all outline-none focus-visible:ring-2 focus-visible:ring-brand-500 text-[10px] font-bold tracking-wider uppercase shadow-sm disabled:opacity-50 disabled:cursor-not-allowed">
        <Download size={14} /> {isExporting ? "Compiling PDF..." : "Download Report"}
      </button>
    </div>
  );
}
