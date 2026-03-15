import { ExternalLink } from "lucide-react";
import { useLanguage } from "@/contexts/LanguageContext";
import { Badge } from "@/components/ui/badge";

interface SourceCardProps {
  articleNumber: string;
  score: number;
  snippet: string;
}

function getScoreColor(score: number) {
  if (score >= 80) return "bg-score-high/15 text-score-high border-score-high/30";
  if (score >= 50) return "bg-score-medium/15 text-score-medium border-score-medium/30";
  return "bg-score-low/15 text-score-low border-score-low/30";
}

export function SourceCard({ articleNumber, score, snippet }: SourceCardProps) {
  const { t } = useLanguage();

  return (
    <div className="group rounded-xl border border-border bg-card p-4 transition-all hover:border-primary/30 hover:shadow-lg hover:shadow-primary/5 animate-slide-up">
      <div className="mb-3 flex items-center justify-between">
        <span className="text-sm font-semibold text-foreground">
          {t("article")} {articleNumber}
        </span>
        <Badge variant="outline" className={`border text-xs ${getScoreColor(score)}`}>
          {score}% {t("match")}
        </Badge>
      </div>
      <p className="mb-3 line-clamp-3 text-sm leading-relaxed text-muted-foreground">
        {snippet}
      </p>
      <button className="flex items-center gap-1.5 text-xs font-medium text-primary transition-colors hover:text-primary/80">
        {t("readMore")}
        <ExternalLink className="h-3 w-3" />
      </button>
    </div>
  );
}
