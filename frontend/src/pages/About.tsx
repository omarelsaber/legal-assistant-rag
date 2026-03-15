import { motion } from "framer-motion";
import { Scale, Target, Layers, Zap, Database, Brain, BarChart3 } from "lucide-react";
import { useLanguage } from "@/contexts/LanguageContext";
import { LandingHeader } from "@/components/legal/LandingHeader";
import { Footer } from "@/components/legal/Footer";

const fadeUp = {
  hidden: { opacity: 0, y: 30 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.12, duration: 0.5, ease: "easeOut" as const },
  }),
};

const About = () => {
  const { language, dir } = useLanguage();
  const isAr = language === "ar";

  const techStack = [
    { icon: Brain, name: "LlamaIndex + Ollama", desc: isAr ? "نماذج ذكاء اصطناعي محلية" : "Local AI Models" },
    { icon: Database, name: "ChromaDB", desc: isAr ? "قاعدة بيانات المتجهات" : "Vector Database" },
    { icon: Zap, name: "FastAPI", desc: isAr ? "واجهة برمجية سريعة" : "High-Performance API" },
    { icon: BarChart3, name: "MLflow + Ragas", desc: isAr ? "تقييم ومراقبة النماذج" : "Model Evaluation & Monitoring" },
    { icon: Layers, name: "React + TypeScript", desc: isAr ? "واجهة مستخدم حديثة" : "Modern Frontend" },
    { icon: Target, name: "RAG Pipeline", desc: isAr ? "استرجاع معزز بالتوليد" : "Retrieval-Augmented Generation" },
  ];

  const steps = [
    {
      num: "01",
      title: isAr ? "اطرح سؤالك القانوني" : "Ask Your Legal Question",
      desc: isAr ? "اكتب سؤالك بالعربية أو الإنجليزية عن أي موضوع في القانون المصري" : "Type your question in Arabic or English about any Egyptian law topic",
    },
    {
      num: "02",
      title: isAr ? "البحث في قاعدة البيانات" : "Vector Search",
      desc: isAr ? "يبحث النظام في آلاف المواد القانونية باستخدام تقنية البحث الدلالي" : "The system searches thousands of legal articles using semantic search",
    },
    {
      num: "03",
      title: isAr ? "توليد الإجابة" : "Generate Answer",
      desc: isAr ? "يقوم نموذج الذكاء الاصطناعي بتحليل النصوص وتقديم إجابة دقيقة" : "The AI model analyzes texts and provides a precise answer",
    },
    {
      num: "04",
      title: isAr ? "عرض المصادر" : "Display Sources",
      desc: isAr ? "يتم عرض المواد القانونية المرجعية مع نسب التطابق" : "Referenced legal articles are displayed with similarity scores",
    },
  ];

  return (
    <div dir={dir} className="min-h-screen bg-background font-arabic">
      <LandingHeader />

      {/* Hero */}
      <section className="relative px-4 pt-32 pb-20 text-center">
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute top-20 start-1/4 h-64 w-64 rounded-full bg-primary/5 blur-3xl" />
        </div>
        <div className="container relative mx-auto max-w-4xl">
          <motion.h1
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-4 text-4xl font-extrabold text-foreground md:text-6xl"
          >
            {isAr ? (
              <>عن <span className="text-primary">المنصة</span></>
            ) : (
              <>About <span className="text-primary">The Platform</span></>
            )}
          </motion.h1>
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="mb-3 text-sm font-semibold uppercase tracking-widest text-primary"
          >
            {isAr ? "تمكين العدالة من خلال الذكاء الاصطناعي" : "Empowering Justice Through AI"}
          </motion.p>
        </div>
      </section>

      {/* Mission */}
      <section className="px-4 pb-20">
        <div className="container mx-auto max-w-3xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="rounded-2xl border border-border bg-card p-8 text-center md:p-12"
          >
            <h2 className="mb-4 text-2xl font-bold text-foreground">
              {isAr ? "مساعد قانوني بالذكاء الاصطناعي" : "An AI Legal Assistant"}
            </h2>
            <p className="mb-8 text-muted-foreground leading-relaxed">
              {isAr
                ? "منصة مفتوحة المصدر مصممة لجعل التوجيه القانوني في متناول الجميع. باستخدام تقنية RAG المدعومة بالذكاء الاصطناعي، تقدم المنصة دعماً قانونياً سريعاً ودقيقاً يناسب احتياجاتك، سواء كنت مواطناً عادياً أو محترفاً قانونياً."
                : "An open-source platform designed to make legal guidance accessible to everyone. Using AI-powered RAG technology, it delivers quick, accurate legal support tailored to your needs, whether you're a layperson or a professional."}
            </p>
            <div className="rounded-xl border border-border bg-secondary/50 p-6">
              <Scale className="mx-auto mb-3 h-8 w-8 text-primary" />
              <h3 className="mb-2 font-bold text-foreground">{isAr ? "مهمتنا" : "Our Mission"}</h3>
              <p className="text-sm italic text-muted-foreground">
                {isAr
                  ? "\"العدالة يجب أن تكون في متناول الجميع. نحن نضمن ألا يتخلف أحد عن الركب في ما يتعلق بالمعرفة القانونية.\""
                  : "\"Justice should be accessible to everyone. We ensure that no one is left behind when it comes to legal knowledge.\""}
              </p>
            </div>
          </motion.div>
        </div>
      </section>

      {/* How it works */}
      <section className="border-y border-border bg-card/30 py-24 px-4">
        <div className="container mx-auto max-w-5xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mb-16 text-center"
          >
            <p className="mb-2 text-sm font-semibold uppercase tracking-widest text-primary">
              {isAr ? "كيف يعمل" : "How It Works"}
            </p>
            <h2 className="text-3xl font-bold text-foreground">{isAr ? "خطوات بسيطة" : "Simple Steps"}</h2>
          </motion.div>
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
            {steps.map((step, i) => (
              <motion.div
                key={step.num}
                custom={i}
                variants={fadeUp}
                initial="hidden"
                whileInView="visible"
                viewport={{ once: true }}
                className="rounded-2xl border border-border bg-card p-6 text-center"
              >
                <span className="mb-3 inline-block text-3xl font-extrabold text-primary/30">{step.num}</span>
                <h3 className="mb-2 font-bold text-foreground">{step.title}</h3>
                <p className="text-sm text-muted-foreground">{step.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Tech Stack */}
      <section className="py-24 px-4">
        <div className="container mx-auto max-w-5xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mb-16 text-center"
          >
            <p className="mb-2 text-sm font-semibold uppercase tracking-widest text-primary">
              {isAr ? "التقنيات المستخدمة" : "Tech Stack"}
            </p>
            <h2 className="text-3xl font-bold text-foreground">{isAr ? "مبني بأحدث التقنيات" : "Built With Modern Tech"}</h2>
          </motion.div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {techStack.map((tech, i) => (
              <motion.div
                key={tech.name}
                custom={i}
                variants={fadeUp}
                initial="hidden"
                whileInView="visible"
                viewport={{ once: true }}
                className="flex items-center gap-4 rounded-xl border border-border bg-card p-5 transition-all hover:border-primary/30"
              >
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                  <tech.icon className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <p className="font-semibold text-foreground">{tech.name}</p>
                  <p className="text-xs text-muted-foreground">{tech.desc}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      <Footer />
    </div>
  );
};

export default About;
