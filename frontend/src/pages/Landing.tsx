import { motion } from "framer-motion";
import { Scale, ArrowLeft, Sparkles, BookOpen, Shield, Cpu, ChevronDown } from "lucide-react";
import { useLanguage } from "@/contexts/LanguageContext";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Footer } from "@/components/legal/Footer";
import { LandingHeader } from "@/components/legal/LandingHeader";

const fadeUp = {
  hidden: { opacity: 0, y: 40 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.15, duration: 0.6, ease: "easeOut" as const },
  }),
};

const Landing = () => {
  const { t, language, dir } = useLanguage();
  const isAr = language === "ar";

  const features = [
    {
      icon: Cpu,
      title: isAr ? "ذكاء اصطناعي متقدم" : "Advanced AI Engine",
      desc: isAr
        ? "مدعوم بنماذج LLM محلية مع تقنية RAG لتحليل دقيق للقوانين المصرية"
        : "Powered by local LLMs with RAG technology for precise Egyptian law analysis",
    },
    {
      icon: BookOpen,
      title: isAr ? "تغطية قانونية شاملة" : "Comprehensive Legal Coverage",
      desc: isAr
        ? "يشمل القانون المدني والجنائي والتجاري والدستوري والمزيد"
        : "Covers Civil, Penal, Corporate, Constitutional law and more",
    },
    {
      icon: Shield,
      title: isAr ? "مصادر موثوقة" : "Verified Sources",
      desc: isAr
        ? "كل إجابة مدعومة بمواد قانونية محددة مع نسب تطابق دقيقة"
        : "Every answer backed by specific legal articles with similarity scores",
    },
    {
      icon: Sparkles,
      title: isAr ? "واجهة احترافية" : "Enterprise-Grade UI",
      desc: isAr
        ? "تصميم عصري يدعم اللغة العربية بالكامل مع وضع داكن أنيق"
        : "Modern design with full Arabic RTL support and elegant dark mode",
    },
  ];

  const stats = [
    { value: "10,000+", label: isAr ? "مادة قانونية" : "Legal Articles" },
    { value: "99.2%", label: isAr ? "دقة التحليل" : "Analysis Accuracy" },
    { value: "24/7", label: isAr ? "متاح دائماً" : "Always Available" },
    { value: "<2s", label: isAr ? "وقت الاستجابة" : "Response Time" },
  ];

  return (
    <div dir={dir} className="min-h-screen bg-transparent font-arabic relative overflow-hidden">
      {/* Cinematic Video Background */}
      <video
        autoPlay
        loop
        muted
        playsInline
        className="pointer-events-none absolute inset-0 h-full w-full object-cover -z-20"
      >
        <source src="/6101361-uhd_2160_4096_30fps.mp4" type="video/mp4" />
      </video>
      <div className="pointer-events-none absolute inset-0 bg-slate-950/80 -z-10" />

      <div className="relative z-10 flex flex-col">
        <LandingHeader />

        {/* Hero Section */}
        <section className="relative overflow-hidden px-4 pt-32 pb-20">

        <div className="container relative mx-auto max-w-5xl text-center">
          <motion.div
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.5 }}
            className="mx-auto mb-8 flex h-20 w-20 items-center justify-center rounded-2xl bg-primary/10 shadow-lg shadow-primary/20"
          >
            <Scale className="h-10 w-10 text-primary" />
          </motion.div>

          <motion.p
            custom={0}
            variants={fadeUp}
            initial="hidden"
            animate="visible"
            className="mb-4 text-sm font-semibold uppercase tracking-widest text-primary"
          >
            {isAr ? "منصة LLM-as-a-Service" : "LLM-as-a-Service Platform"}
          </motion.p>

          <motion.h1
            custom={1}
            variants={fadeUp}
            initial="hidden"
            animate="visible"
            className="mb-6 text-4xl font-extrabold leading-tight text-foreground md:text-6xl lg:text-7xl"
          >
            {isAr ? (
              <>
                طريقة جديدة
                <br />
                <span className="text-primary">للبحث القانوني</span>
              </>
            ) : (
              <>
                A New Way of
                <br />
                <span className="text-primary">Legal Research</span>
              </>
            )}
          </motion.h1>

          <motion.p
            custom={2}
            variants={fadeUp}
            initial="hidden"
            animate="visible"
            className="mx-auto mb-10 max-w-2xl text-lg text-muted-foreground"
          >
            {isAr
              ? "مساعد قانوني مصري مدعوم بالذكاء الاصطناعي. يستخدم تقنية RAG المتقدمة لتقديم استشارات قانونية دقيقة وموثوقة من القانون المصري بالكامل."
              : "An Egyptian AI-powered legal assistant using advanced RAG technology to deliver accurate, reliable legal consultations from the entire Egyptian Legal Corpus."}
          </motion.p>

          <motion.div
            custom={3}
            variants={fadeUp}
            initial="hidden"
            animate="visible"
            className="flex flex-col items-center justify-center gap-4 sm:flex-row"
          >
            <Link to="/chat">
              <Button size="lg" className="gap-2 rounded-xl px-8 py-6 text-base font-semibold shadow-lg shadow-primary/25">
                {isAr ? "ابدأ الآن" : "Get Started"}
                <ArrowLeft className={`h-5 w-5 ${!isAr ? "rotate-180" : ""}`} />
              </Button>
            </Link>
            <Link to="/about">
              <Button variant="outline" size="lg" className="rounded-xl px-8 py-6 text-base">
                {isAr ? "اعرف المزيد" : "Learn More"}
              </Button>
            </Link>
          </motion.div>

          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 1.2, duration: 0.8 }}
            className="mt-16"
          >
            <ChevronDown className="mx-auto h-6 w-6 animate-bounce text-muted-foreground" />
          </motion.div>
        </div>
      </section>

      {/* Stats Section */}
      <section className="border-y border-border bg-card/50 py-16">
        <div className="container mx-auto max-w-5xl px-4">
          <div className="grid grid-cols-2 gap-8 md:grid-cols-4">
            {stats.map((stat, i) => (
              <motion.div
                key={stat.label}
                custom={i}
                variants={fadeUp}
                initial="hidden"
                whileInView="visible"
                viewport={{ once: true }}
                className="text-center"
              >
                <p className="text-3xl font-extrabold text-primary md:text-4xl">{stat.value}</p>
                <p className="mt-1 text-sm text-muted-foreground">{stat.label}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-24 px-4">
        <div className="container mx-auto max-w-5xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mb-16 text-center"
          >
            <p className="mb-2 text-sm font-semibold uppercase tracking-widest text-primary">
              {isAr ? "المميزات" : "Features"}
            </p>
            <h2 className="text-3xl font-bold text-foreground md:text-4xl">
              {isAr ? "لماذا تختار منصتنا؟" : "Why Choose Our Platform?"}
            </h2>
          </motion.div>

          <div className="grid gap-6 md:grid-cols-2">
            {features.map((f, i) => (
              <motion.div
                key={f.title}
                custom={i}
                variants={fadeUp}
                initial="hidden"
                whileInView="visible"
                viewport={{ once: true }}
                className="group rounded-2xl border border-border bg-card p-8 transition-all hover:border-primary/30 hover:shadow-xl hover:shadow-primary/5"
              >
                <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 transition-colors group-hover:bg-primary/20">
                  <f.icon className="h-6 w-6 text-primary" />
                </div>
                <h3 className="mb-2 text-lg font-bold text-foreground">{f.title}</h3>
                <p className="text-sm leading-relaxed text-muted-foreground">{f.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-24 px-4">
        <div className="container mx-auto max-w-3xl">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5 }}
            className="rounded-3xl border border-border bg-card p-12 text-center shadow-2xl shadow-primary/5"
          >
            <Scale className="mx-auto mb-6 h-12 w-12 text-primary" />
            <h2 className="mb-4 text-2xl font-bold text-foreground md:text-3xl">
              {isAr ? "انضم لمستقبل المعرفة القانونية" : "Join the Future of Legal Knowledge"}
            </h2>
            <p className="mx-auto mb-8 max-w-lg text-muted-foreground">
              {isAr
                ? "ابدأ الآن في استخدام مساعدك القانوني الذكي للحصول على استشارات فورية ودقيقة"
                : "Start using your intelligent legal assistant for instant, accurate consultations"}
            </p>
            <Link to="/chat">
              <Button size="lg" className="rounded-xl px-10 py-6 text-base font-semibold shadow-lg shadow-primary/25">
                {isAr ? "ابدأ المحادثة" : "Start Chat"}
              </Button>
            </Link>
          </motion.div>
        </div>
      </section>

      <Footer />
      </div>
    </div>
  );
};

export default Landing;
