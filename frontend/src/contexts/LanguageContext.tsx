import { createContext, useContext, useState, ReactNode } from "react";

type Language = "ar" | "en";

interface LanguageContextType {
  language: Language;
  dir: "rtl" | "ltr";
  toggleLanguage: () => void;
  t: (key: string) => string;
}

const translations: Record<string, Record<Language, string>> = {
  title: { ar: "المستشار القانوني المصري بالذكاء الاصطناعي", en: "Egyptian AI Legal Assistant" },
  subtitle: { ar: "مساعدك القانوني الذكي", en: "Your Intelligent Legal Advisor" },
  placeholder: { ar: "اكتب سؤالك القانوني هنا...", en: "Type your legal question here..." },
  send: { ar: "إرسال", en: "Send" },
  sources: { ar: "المصادر القانونية", en: "Legal Sources" },
  readMore: { ar: "اقرأ المزيد", en: "Read More" },
  article: { ar: "المادة", en: "Article" },
  match: { ar: "تطابق", en: "match" },
  thinking: { ar: "جاري التحليل القانوني...", en: "Analyzing legal context..." },
  welcome: { ar: "مرحباً! أنا مساعدك القانوني المصري. كيف يمكنني مساعدتك اليوم؟", en: "Welcome! I'm your Egyptian legal assistant. How can I help you today?" },
  welcomeHint: { ar: "اسألني عن أي موضوع قانوني مصري", en: "Ask me about any Egyptian legal topic" },
};

const LanguageContext = createContext<LanguageContextType | undefined>(undefined);

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguage] = useState<Language>("ar");

  const toggleLanguage = () => setLanguage((l) => (l === "ar" ? "en" : "ar"));
  const dir = language === "ar" ? "rtl" : "ltr";
  const t = (key: string) => translations[key]?.[language] || key;

  return (
    <LanguageContext.Provider value={{ language, dir, toggleLanguage, t }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  const ctx = useContext(LanguageContext);
  if (!ctx) throw new Error("useLanguage must be used within LanguageProvider");
  return ctx;
}
