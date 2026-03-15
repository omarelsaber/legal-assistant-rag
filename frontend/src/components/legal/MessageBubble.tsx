import { Scale, User } from "lucide-react";

interface Source {
  id: number;
  articleNumber: string;
  score: number;
  snippet: string;
}

interface MessageBubbleProps {
  role: "user" | "ai";
  content: string;
  sources?: Source[];
}

/**
 * Parses the LLM's Markdown-lite output into React elements.
 *
 * Handles:
 *   **bold text**  → <strong> header block with bottom border
 *   - list item    → RTL-correct bullet (right-side dot, right indent)
 *   \n\n           → paragraph break (visual spacing between sections)
 *   \n             → line break within a section
 *
 * Arabic-specific decisions:
 *   - Bullets use margin-right (not margin-left) because Arabic reads RTL
 *   - The bullet marker (•) is positioned on the RIGHT of each item,
 *     which is the "start" edge in RTL layout
 *   - Bold headers use border-b-2 with primary color for visual hierarchy
 */
const parseMarkdown = (text: string): React.ReactNode[] => {
  // Split on bold markers (**...**) and list items (- ...).
  // Capturing group means the matched delimiters are included in the array.
  const parts = text.split(/(\*\*.*?\*\*|- .*)/g);

  return parts
    .filter((part) => part !== "") // remove empty strings from split artefacts
    .map((part, index) => {
      // ── Bold section header: **النص** ──────────────────────────────────────
      if (part.startsWith("**") && part.endsWith("**")) {
        const headerText = part.slice(2, -2);
        return (
          <strong
            key={index}
            className="font-bold text-primary block mt-5 mb-1 pb-1 border-b border-primary/20"
          >
            {headerText}
          </strong>
        );
      }

      // ── RTL bullet list item: - النص ───────────────────────────────────────
      // The bullet (•) is placed on the RIGHT (start side in RTL).
      // pr-5 = padding-right to make room for the bullet marker.
      // mr-0 ml-auto with inline-block on the marker achieves RTL bullet.
      if (part.startsWith("- ")) {
        return (
          <span
            key={index}
            className="flex items-start gap-2 mb-1 leading-relaxed"
            style={{ direction: "rtl" }}
          >
            <span className="text-primary mt-1 shrink-0 select-none">•</span>
            <span>{part.substring(2)}</span>
          </span>
        );
      }

      // ── Plain text with newline handling ────────────────────────────────────
      // Split on double-newlines first (paragraph breaks), then single newlines.
      const paragraphs = part.split(/\n\n+/);
      return (
        <span key={index}>
          {paragraphs.map((paragraph, pIdx) => {
            if (!paragraph.trim()) return null;
            const lines = paragraph.split("\n");
            return (
              // Each paragraph gets bottom margin to separate sections visually
              <span
                key={pIdx}
                className={`block leading-relaxed ${pIdx < paragraphs.length - 1 ? "mb-3" : ""}`}
              >
                {lines.map((line, lIdx) => (
                  <span key={lIdx}>
                    {line}
                    {lIdx < lines.length - 1 && <br />}
                  </span>
                ))}
              </span>
            );
          })}
        </span>
      );
    });
};

export function MessageBubble({ role, content, sources }: MessageBubbleProps) {
  const isUser = role === "user";

  return (
    <div
      className={`flex w-full ${isUser ? "justify-end" : "justify-start"} mb-4`}
    >
      <div
        className={`flex items-start gap-3 animate-fade-in ${
          isUser ? "flex-row-reverse" : ""
        } max-w-[80%]`}
      >
        {/* Avatar */}
        <div
          className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${
            isUser ? "bg-primary" : "bg-primary/10"
          }`}
        >
          {isUser ? (
            <User className="h-4 w-4 text-primary-foreground" />
          ) : (
            <Scale className="h-4 w-4 text-primary" />
          )}
        </div>

        {/* Message bubble */}
        <div
          dir="rtl"
          className={`w-fit rounded-3xl px-6 py-4 tracking-wide ${
            isUser
              ? "rounded-te-none bg-slate-800 text-white text-sm leading-relaxed"
              : "rounded-ts-none bg-chat-ai border border-white/5 shadow-xl text-chat-ai-foreground text-base"
          }`}
        >
          {isUser ? (
            // User messages: plain text, RTL
            <span className="leading-relaxed">{content}</span>
          ) : content ? (
            // AI messages: parsed Markdown with Arabic formatting
            <div className="space-y-0.5">
              {parseMarkdown(content)}
            </div>
          ) : (
            // Loading indicator — shown while waiting for the first token
            <div className="flex items-center gap-2 py-1">
              <span className="h-2 w-2 rounded-full bg-primary/60 animate-bounce [animation-delay:-0.3s]" />
              <span className="h-2 w-2 rounded-full bg-primary/60 animate-bounce [animation-delay:-0.15s]" />
              <span className="h-2 w-2 rounded-full bg-primary/60 animate-bounce" />
            </div>
          )}
          {/* Sources panel — currently hidden for clean UX */}
          {/* Uncomment to re-enable source citations:
          {sources && sources.length > 0 && (
            <div className="mt-4 pt-3 border-t border-white/10 space-y-1">
              {sources.map((s) => (
                <div key={s.id} className="text-xs text-muted-foreground">
                  {s.articleNumber} — {s.snippet.slice(0, 80)}…
                </div>
              ))}
            </div>
          )} */}
        </div>
      </div>
    </div>
  );
}
