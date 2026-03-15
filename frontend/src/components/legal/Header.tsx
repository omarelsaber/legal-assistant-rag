import { Scale, Globe } from "lucide-react";
import { useLanguage } from "@/contexts/LanguageContext";
import { Button } from "@/components/ui/button";

export function Header() {
  const { t, language, toggleLanguage } = useLanguage();

  return (
    <header className="sticky top-0 z-50 border-b border-header-border bg-header/80 backdrop-blur-xl">
      <div className="container flex h-16 items-center justify-between px-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
            <Scale className="h-5 w-5 text-primary" />
          </div>
          <div>
            <h1 className="text-sm font-bold leading-tight text-foreground md:text-base">
              {t("title")}
            </h1>
            <p className="hidden text-xs text-muted-foreground sm:block">
              {t("subtitle")}
            </p>
          </div>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={toggleLanguage}
          className="gap-2 text-muted-foreground hover:text-foreground"
          aria-label="Toggle language"
        >
          <Globe className="h-4 w-4" />
          <span className="text-xs font-medium">{language === "ar" ? "EN" : "عربي"}</span>
        </Button>
      </div>
    </header>
  );
}
