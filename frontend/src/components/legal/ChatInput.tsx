import { useState, FormEvent } from "react";
import { SendHorizontal } from "lucide-react";
import { useLanguage } from "@/contexts/LanguageContext";
import { Button } from "@/components/ui/button";

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
}

export function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [value, setValue] = useState("");
  const { t } = useLanguage();

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
  };

  return (
    <div className="absolute bottom-8 left-0 right-0 z-50 flex justify-center px-4 pointer-events-none animate-slide-up">
      <form onSubmit={handleSubmit} className="pointer-events-auto w-full max-w-3xl flex items-center gap-2 p-2 rounded-full border border-white/10 bg-black/60 backdrop-blur-2xl shadow-2xl transition-all hover:border-white/20 focus-within:border-primary/50 focus-within:bg-black/80">
        <input
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={t("placeholder")}
          disabled={disabled}
          className="flex-1 bg-transparent px-6 py-3 text-base text-foreground placeholder:text-muted-foreground focus:outline-none disabled:opacity-50"
          aria-label={t("placeholder")}
        />
        <Button
          type="submit"
          size="icon"
          disabled={!value.trim() || disabled}
          className="h-12 w-12 shrink-0 rounded-full bg-primary/10 text-primary hover:bg-primary hover:text-primary-foreground transition-all duration-300"
          aria-label={t("send")}
        >
          <SendHorizontal className="h-5 w-5" />
        </Button>
      </form>
    </div>
  );
}
