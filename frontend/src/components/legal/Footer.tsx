import { Scale, Mail, Github, Linkedin } from "lucide-react";
import { useLanguage } from "@/contexts/LanguageContext";
import { Link } from "react-router-dom";

export function Footer() {
  const { language } = useLanguage();
  const isAr = language === "ar";

  const quickLinks = [
    { label: isAr ? "الرئيسية" : "Home", to: "/" },
    { label: isAr ? "عن المنصة" : "About", to: "/about" },
    { label: isAr ? "المحادثة" : "Chat", to: "/chat" },
  ];

  const legalCoverage = [
    isAr ? "الدستور المصري" : "Egyptian Constitution",
    isAr ? "القانون المدني" : "Civil Law",
    isAr ? "القانون الجنائي" : "Penal Law",
    isAr ? "قانون الشركات" : "Corporate Law",
  ];

  return (
    <footer className="border-t border-border bg-card/50">
      <div className="container mx-auto max-w-6xl px-4 py-16">
        <div className="grid gap-10 sm:grid-cols-2 lg:grid-cols-4">
          {/* Brand */}
          <div>
            <div className="mb-4 flex items-center gap-2">
              <Scale className="h-5 w-5 text-primary" />
              <span className="font-bold text-foreground">
                {isAr ? "المستشار القانوني" : "Legal Assistant"}
              </span>
            </div>
            <p className="text-sm leading-relaxed text-muted-foreground">
              {isAr
                ? "نجعل المعرفة القانونية في متناول الجميع من خلال الذكاء الاصطناعي."
                : "Making legal knowledge accessible to everyone through AI-powered assistance."}
            </p>
          </div>

          {/* Quick Links */}
          <div>
            <h3 className="mb-4 font-bold text-foreground">{isAr ? "روابط سريعة" : "Quick Links"}</h3>
            <ul className="space-y-2">
              {quickLinks.map((link) => (
                <li key={link.to}>
                  <Link
                    to={link.to}
                    className="text-sm text-muted-foreground transition-colors hover:text-primary"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Legal Coverage */}
          <div>
            <h3 className="mb-4 font-bold text-foreground">{isAr ? "التغطية القانونية" : "Legal Coverage"}</h3>
            <ul className="space-y-2">
              {legalCoverage.map((item) => (
                <li key={item} className="text-sm text-muted-foreground">{item}</li>
              ))}
            </ul>
          </div>

          {/* Contact */}
          <div>
            <h3 className="mb-4 font-bold text-foreground">{isAr ? "تواصل معنا" : "Connect"}</h3>
            <div className="space-y-3">
              <a
                href="mailto:omarelsaber0@gmail.com"
                className="flex items-center gap-2 rounded-lg border border-border bg-secondary/50 px-4 py-2.5 text-sm text-muted-foreground transition-all hover:border-primary/30 hover:text-foreground"
              >
                <Mail className="h-4 w-4 text-primary" />
                omarelsaber0@gmail.com
              </a>
              <a
                href="https://github.com/omarelsaber"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 rounded-lg border border-border bg-secondary/50 px-4 py-2.5 text-sm text-muted-foreground transition-all hover:border-primary/30 hover:text-foreground"
              >
                <Github className="h-4 w-4" />
                GitHub
              </a>
              <a
                href="https://www.linkedin.com/in/omar-elsaber/"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 rounded-lg border border-border bg-secondary/50 px-4 py-2.5 text-sm text-muted-foreground transition-all hover:border-primary/30 hover:text-foreground"
              >
                <Linkedin className="h-4 w-4 text-[hsl(210,80%,55%)]" />
                LinkedIn
              </a>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom bar */}
      <div className="border-t border-border">
        <div className="container mx-auto flex flex-col items-center justify-between gap-4 px-4 py-6 sm:flex-row">
          <p className="text-xs text-muted-foreground">
            © 2024 {isAr ? "المستشار القانوني المصري" : "Egyptian AI Legal Assistant"}. {isAr ? "جميع الحقوق محفوظة." : "All rights reserved."}
          </p>
          <div className="flex gap-6 text-xs text-muted-foreground">
            <span className="cursor-pointer hover:text-foreground">{isAr ? "سياسة الخصوصية" : "Privacy Policy"}</span>
            <span className="cursor-pointer hover:text-foreground">{isAr ? "شروط الاستخدام" : "Terms of Service"}</span>
          </div>
        </div>
      </div>

      {/* Disclaimer */}
      <div className="border-t border-border bg-secondary/30">
        <div className="container mx-auto px-4 py-4">
          <p className="text-xs leading-relaxed text-muted-foreground">
            <span className="font-bold text-foreground">{isAr ? "إخلاء مسؤولية:" : "Legal Disclaimer:"}</span>{" "}
            {isAr
              ? "هذا المساعد القانوني مصمم لتقديم معلومات قانونية عامة ولا يشكل استشارة قانونية. للمسائل القانونية المحددة، يرجى استشارة محامٍ مؤهل."
              : "This AI legal assistant is designed to provide general legal information and should not be relied upon as legal advice. For specific legal matters, please consult with a qualified attorney."}
          </p>
        </div>
      </div>
    </footer>
  );
}
