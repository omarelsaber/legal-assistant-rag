import { Scale, Globe } from "lucide-react";
import { useLanguage } from "@/contexts/LanguageContext";
import { Button } from "@/components/ui/button";
import { Link, useLocation } from "react-router-dom";
import { cn } from "@/lib/utils";

export function LandingHeader() {
  const { language, toggleLanguage } = useLanguage();
  const isAr = language === "ar";
  const location = useLocation();

  const navLinks = [
    { label: isAr ? "الرئيسية" : "Home", to: "/" },
    { label: isAr ? "عن المنصة" : "About", to: "/about" },
    { label: isAr ? "المحادثة" : "Chat", to: "/chat" },
  ];

  return (
    <header className="fixed top-0 z-50 w-full border-b border-header-border bg-header/80 backdrop-blur-xl">
      <div className="container mx-auto flex h-16 items-center justify-between px-4">
        <Link to="/" className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10">
            <Scale className="h-5 w-5 text-primary" />
          </div>
          <div>
            <span className="text-sm font-bold text-foreground">
              {isAr ? "المستشار القانوني" : "Legal Assistant"}
            </span>
            <p className="hidden text-[10px] text-primary sm:block">
              {isAr ? "مساعد قانوني بالذكاء الاصطناعي" : "AI Legal Assistant"}
            </p>
          </div>
        </Link>

        <nav className="hidden items-center gap-1 md:flex">
          {navLinks.map((link) => (
            <Link
              key={link.to}
              to={link.to}
              className={cn(
                "rounded-lg px-4 py-2 text-sm transition-colors hover:text-foreground",
                location.pathname === link.to
                  ? "text-foreground font-medium"
                  : "text-muted-foreground"
              )}
            >
              {link.label}
            </Link>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={toggleLanguage}
            className="gap-2 text-muted-foreground hover:text-foreground"
          >
            <Globe className="h-4 w-4" />
            <span className="text-xs font-medium">{language === "ar" ? "EN" : "عربي"}</span>
          </Button>
        </div>
      </div>
    </header>
  );
}
