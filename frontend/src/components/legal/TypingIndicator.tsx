import { useLanguage } from "@/contexts/LanguageContext";
import { Scale } from "lucide-react";

export function TypingIndicator() {
  const { t } = useLanguage();

  return (
    <div className="flex items-start gap-3 animate-fade-in">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10">
        <Scale className="h-4 w-4 text-primary" />
      </div>
      <div className="rounded-2xl rounded-ts-none bg-chat-ai px-4 py-3">
        <div className="flex items-center gap-2">
          <div className="flex gap-1">
            <span className="typing-dot h-2 w-2 rounded-full bg-primary" />
            <span className="typing-dot h-2 w-2 rounded-full bg-primary" />
            <span className="typing-dot h-2 w-2 rounded-full bg-primary" />
          </div>
          <span className="text-xs text-muted-foreground">{t("thinking")}</span>
        </div>
      </div>
    </div>
  );
}
