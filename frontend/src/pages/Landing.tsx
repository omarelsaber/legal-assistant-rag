/**
 * Landing.tsx — Hero / landing page for the Egyptian Law Assistant.
 *
 * All Lovable badges, logos, and branding have been removed.
 * Replaced with a clean Arabic legal-consultant identity.
 */

import { Scale, MessageSquare, BookOpen, Shield } from "lucide-react";
import { useNavigate } from "react-router-dom";

const FEATURES = [
  {
    icon: BookOpen,
    title: "مبني على التشريعات الرسمية",
    description: "إجابات مستندة حصراً إلى النصوص القانونية المصرية الرسمية.",
  },
  {
    icon: MessageSquare,
    title: "محادثة باللغة العربية",
    description: "اسأل بلغتك العامية أو الفصحى — النظام يفهم كلاهما.",
  },
  {
    icon: Shield,
    title: "لا اجتهاد بدون سند",
    description: "كل حكم مقرون برقم المادة والقانون المصدر لسهولة التحقق.",
  },
];

export default function Landing() {
  const navigate = useNavigate();

  return (
    <main
      dir="rtl"
      className="flex flex-col items-center min-h-[calc(100vh-4rem)]
                 text-foreground relative overflow-hidden"
    >
      {/* Cinematic Video Background */}
      <video
        autoPlay
        loop
        muted
        playsInline
        className="absolute inset-0 w-full h-full object-cover z-0"
      >
        <source src="/home.mp4" type="video/mp4" />
      </video>
      <div className="absolute inset-0 bg-black/70 z-0" />

      <div className="relative z-10 w-full flex flex-col items-center">
      {/* ── Hero ──────────────────────────────────────────────────── */}
      <section className="flex flex-col items-center text-center px-4
                           pt-24 pb-16 max-w-3xl mx-auto">

        {/* Icon */}
        <div className="flex h-20 w-20 items-center justify-center rounded-2xl
                        bg-primary/10 ring-1 ring-primary/20 mb-8">
          <Scale className="h-10 w-10 text-primary" aria-hidden />
        </div>

        {/* Headline */}
        <h1 className="text-4xl md:text-5xl font-extrabold tracking-tight
                       text-foreground mb-4 leading-tight">
          المستشار القانوني الذكي
        </h1>

        {/* Sub-headline */}
        <p className="text-lg text-muted-foreground max-w-xl leading-relaxed mb-10">
          استشارات قانونية فورية مبنية على التشريعات المصرية الرسمية —
          احصل على إجابة دقيقة مع المادة والقانون في ثوانٍ.
        </p>

        {/* CTA */}
        <button
          onClick={() => navigate("/chat")}
          className="inline-flex items-center gap-3 px-8 py-4
                     bg-primary text-primary-foreground font-semibold
                     rounded-2xl shadow-lg hover:bg-primary/90
                     active:scale-95 transition-all text-base"
        >
          <MessageSquare className="h-5 w-5" aria-hidden />
          ابدأ استشارتك الآن
        </button>

        {/* Disclaimer */}
        <p className="mt-5 text-xs text-muted-foreground/60 max-w-md">
          هذه الأداة للأغراض المعلوماتية فقط ولا تُغني عن استشارة محامٍ مرخّص.
        </p>
      </section>

      {/* ── Features ──────────────────────────────────────────────── */}
      <section className="w-full max-w-4xl px-4 pb-20 mx-auto">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {FEATURES.map(({ icon: Icon, title, description }) => (
            <div
              key={title}
              className="flex flex-col items-start gap-3 p-6
                         rounded-2xl bg-white/[0.03] border border-white/[0.07]
                         hover:bg-white/[0.06] transition-colors"
            >
              <div className="flex h-10 w-10 items-center justify-center
                              rounded-xl bg-primary/10">
                <Icon className="h-5 w-5 text-primary" aria-hidden />
              </div>
              <h3 className="font-semibold text-foreground text-sm">{title}</h3>
              <p className="text-xs text-muted-foreground leading-relaxed">
                {description}
              </p>
            </div>
          ))}
        </div>
      </section>
      </div>
    </main>
  );
}
