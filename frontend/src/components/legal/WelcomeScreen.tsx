import { Scale, MessageSquare, BookOpen, Shield } from "lucide-react";
import { useLanguage } from "@/contexts/LanguageContext";

export function WelcomeScreen() {
  const { t } = useLanguage();

  const features = [
    { icon: MessageSquare, label: { ar: "استشارات قانونية فورية", en: "Instant Legal Consultation" } },
    { icon: BookOpen, label: { ar: "مراجع من القانون المصري", en: "Egyptian Law References" } },
    { icon: Shield, label: { ar: "تحليل دقيق وموثوق", en: "Accurate & Reliable Analysis" } },
  ];

  const { language } = useLanguage();

  return (
    <div className="flex flex-col items-center justify-center text-center space-y-6 w-full max-w-3xl mx-auto mt-20">
      <div className="flex h-16 w-16 items-center justify-center">
        <Scale className="h-10 w-10 text-primary drop-shadow-md" />
      </div>
      <div>
        <h2 className="mb-2 text-3xl font-bold text-white drop-shadow-lg">{t("welcome")}</h2>
        <p className="text-lg text-gray-200 drop-shadow-md font-medium">{t("welcomeHint")}</p>
      </div>
      <div className="flex flex-wrap justify-center gap-4 pt-4">
        {features.map(({ icon: Icon, label }) => (
          <div
            key={label.en}
            className="flex items-center gap-2 px-4 py-3"
          >
            <Icon className="h-5 w-5 text-primary" />
            <span className="text-sm font-medium text-white drop-shadow-md">{label[language]}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
