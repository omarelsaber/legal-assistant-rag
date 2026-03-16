import { useState, useRef, useEffect, useCallback } from "react";
import { useLanguage } from "@/contexts/LanguageContext";
import { ChatInput } from "@/components/legal/ChatInput";
import { MessageBubble } from "@/components/legal/MessageBubble";
import { TypingIndicator } from "@/components/legal/TypingIndicator";
import { ResponseDisplay } from "@/components/legal/ResponseDisplay";
import { WelcomeScreen } from "@/components/legal/WelcomeScreen";

interface Source {
  id: number;
  articleNumber: string;
  score: number;
  snippet: string;
}

interface Message {
  id: number;
  role: "user" | "ai";
  content: string;
  sources?: Source[];
}



const Index = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const { dir, language } = useLanguage();

  const scrollToBottom = useCallback(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading, scrollToBottom]);

  const handleSend = async (text: string) => {
    const userMsg: Message = { id: Date.now(), role: "user", content: text };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const res = await fetch("http://localhost:8000/api/v1/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: text, top_k: 5 }),
      });
      const data = await res.json();
      // Map API source_chunks to the frontend's expected sources format
      const sources = Array.isArray(data.source_chunks)
        ? data.source_chunks.map((chunk) => ({
            id: chunk.chunk_id,
            articleNumber: chunk.article_number ?? "",
            score: chunk.metadata?.similarity_score ?? 0,
            snippet: chunk.content,
          }))
        : [];
      const aiMsg: Message = {
        id: Date.now() + 1,
        role: "ai",
        content: data.answer,
        sources,
      };
      setMessages((prev) => [...prev, aiMsg]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { id: Date.now() + 2, role: "ai", content: "Error: Could not get a response from the server." },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const hasMessages = messages.length > 0;

  return (
    <div dir={dir} className="flex h-screen flex-col bg-transparent font-arabic relative overflow-hidden">
      {/* Cinematic Video Background */}
      <video
        autoPlay
        loop
        muted
        playsInline
        className="pointer-events-none absolute inset-0 h-full w-full object-cover -z-20"
      >
        <source src="/chat.mp4" type="video/mp4" />
      </video>
      <div className="pointer-events-none absolute inset-0 bg-slate-950/80 -z-10" />

      <div className="relative z-10 flex flex-1 flex-col h-full">
        <main className="flex flex-1 flex-col overflow-y-auto scrollbar-thin pt-20 pb-4">
        {!hasMessages && !loading ? (
          <WelcomeScreen />
        ) : (
          <div className="container flex flex-col gap-6 px-6 py-8 max-w-4xl mx-auto backdrop-blur-xl bg-white/[0.02] border border-white/[0.05] shadow-2xl rounded-3xl mb-4 mt-2 min-h-[60vh]">
            {messages.map((msg) => (
              <div key={msg.id}>
                <MessageBubble role={msg.role} content={msg.content} sources={msg.sources} />
              </div>
            ))}
            {loading && <TypingIndicator />}
            <div ref={chatEndRef} />
          </div>
        )}
      </main>

      <div className="relative z-20">
        <ChatInput onSend={handleSend} disabled={loading} />
      </div>
    </div>
  </div>
  );
};

export default Index;
