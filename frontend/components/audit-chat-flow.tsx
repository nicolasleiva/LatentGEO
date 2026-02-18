"use client";

import { useState, useEffect, useRef } from "react";
import { Input } from "@/components/ui/input";
import { Send, Sparkles, Globe, Flag, CheckCircle } from "lucide-react";
import { API_URL } from "@/lib/api";
import { fetchWithBackendAuth } from "@/lib/backend-auth";

interface AuditChatFlowProps {
  auditId: number | string;
  onComplete: () => void;
}

interface Message {
  role: "user" | "assistant";
  content: string;
  typing?: boolean;
}

const steps = [
  { id: "competitors", label: "Competitors", icon: Globe },
  { id: "market", label: "Markets", icon: Flag },
  { id: "done", label: "Launch", icon: CheckCircle },
] as const;

export function AuditChatFlow({ auditId, onComplete }: AuditChatFlowProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [config, setConfig] = useState({
    competitors: [] as string[],
    market: "",
  });
  const [step, setStep] = useState<"competitors" | "market" | "done">(
    "competitors",
  );
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const hasInitialized = useRef(false);

  useEffect(() => {
    if (hasInitialized.current) return;
    hasInitialized.current = true;

    sendAIMessage(
      "Welcome to LatentGEO.ai. Would you like to add competitor URLs for comparison? Paste URLs separated by commas, or type 'no' to skip.",
    );
    setStep("competitors");
  }, []);

  useEffect(() => {
    const container = messagesContainerRef.current;
    if (!container) return;
    const distanceFromBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight;
    const isNearBottom = distanceFromBottom < 120;
    if (isNearBottom) {
      container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });
    }
  }, [messages]);

  const sendAIMessage = (content: string) => {
    setIsTyping(true);
    setMessages((prev) => [
      ...prev,
      { role: "assistant", content, typing: true },
    ]);

    setTimeout(() => {
      setMessages((prev) => {
        const newMessages = [...prev];
        const lastMsg = newMessages[newMessages.length - 1];
        if (lastMsg?.typing) {
          lastMsg.typing = false;
        }
        return newMessages;
      });
      setIsTyping(false);
    }, 300);
  };

  const handleSend = async () => {
    if (!input.trim() || isTyping) return;

    const userMessage = input.trim();
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setInput("");

    if (step === "competitors") {
      if (
        userMessage.toLowerCase().includes("no") ||
        userMessage.toLowerCase().includes("skip")
      ) {
        setStep("market");
        sendAIMessage(
          "Got it. Which target markets should we prioritize? (e.g., US, LATAM, Europe) or type 'no'.",
        );
      } else {
        const urls = userMessage
          .split(",")
          .map((u) => {
            let url = u.trim();
            if (url && !url.startsWith("http")) {
              url = "https://" + url;
            }
            return url;
          })
          .filter(
            (u) =>
              u &&
              (u.includes(".") ||
                u.includes("localhost") ||
                u.includes("127.0.0.1")),
          );
        setConfig((prev) => ({ ...prev, competitors: urls }));
        setStep("market");
        sendAIMessage(
          `Noted. I've added ${urls.length} competitor${urls.length === 1 ? "" : "s"}. Now choose target markets (e.g., US, LATAM, Europe) or type 'no'.`,
        );
      }
    } else if (step === "market") {
      const market = userMessage.toLowerCase().includes("no")
        ? ""
        : userMessage;
      setConfig((prev) => ({ ...prev, market }));
      setStep("done");
      sendAIMessage(
        "Confirmed. Launching your comprehensive audit now. This takes a few minutes.",
      );

      try {
        const apiUrl = API_URL;

        const isValidId = (id: number | string): boolean => {
          if (typeof id === "number") return !isNaN(id) && id > 0;
          if (typeof id === "string")
            return /^\d+$/.test(id) && parseInt(id, 10) > 0;
          return false;
        };

        if (auditId && isValidId(auditId)) {
          await fetchWithBackendAuth(`${apiUrl}/api/audits/chat/config`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              audit_id: Number(auditId),
              language: "en",
              competitors:
                config.competitors.length > 0 ? config.competitors : null,
              market: market || null,
            }),
          });
          onComplete();
        } else {
          const createResponse = await fetchWithBackendAuth(
            `${apiUrl}/api/audits`,
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                url: typeof auditId === "string" ? auditId : "",
                language: "en",
                competitors:
                  config.competitors.length > 0 ? config.competitors : null,
                market: market || null,
              }),
            },
          );
          const audit = await createResponse.json();
          window.location.href = `/audits/${audit.id}`;
        }
      } catch (error) {
        console.error("Error:", error);
        onComplete();
      }
    }
  };

  const currentStepIndex = steps.findIndex((item) => item.id === step);

  return (
    <div className="grid gap-8 lg:grid-cols-[280px_minmax(0,1fr)] glass-card p-5 sm:p-6 lg:p-8 lg:min-h-[72vh]">
      <div className="space-y-6">
        <div>
          <div className="flex items-center gap-2 text-sm uppercase tracking-widest text-muted-foreground">
            <Sparkles className="w-4 h-4 text-brand" />
            AI intake
          </div>
          <h2 className="text-2xl lg:text-3xl font-semibold mt-2">
            Audit configuration
          </h2>
          <p className="text-sm text-muted-foreground mt-2">
            Two quick questions to personalize your analysis.
          </p>
        </div>

        <div className="space-y-3">
          {steps.map((item, index) => {
            const Icon = item.icon;
            const isActive = index === currentStepIndex;
            const isComplete = index < currentStepIndex;
            return (
              <div
                key={item.id}
                className={`flex items-center gap-3 rounded-lg border px-3 py-2 text-sm ${
                  isActive
                    ? "border-brand/40 bg-brand/10 text-foreground"
                    : isComplete
                      ? "border-border bg-background/60 text-muted-foreground"
                      : "border-border/70 text-muted-foreground"
                }`}
              >
                <div
                  className={`h-8 w-8 rounded-full flex items-center justify-center ${
                    isActive
                      ? "bg-brand text-brand-foreground"
                      : "bg-foreground/5 text-muted-foreground"
                  }`}
                >
                  <Icon className="h-4 w-4" />
                </div>
                <div className="flex-1">
                  <p className="font-medium">{item.label}</p>
                </div>
                {isComplete && <CheckCircle className="h-4 w-4 text-brand" />}
              </div>
            );
          })}
        </div>
      </div>

      <div className="flex flex-col min-h-[560px] h-[68vh] max-h-[860px] bg-background/70 border border-border/70 rounded-2xl overflow-hidden">
        <div className="border-b border-border/70 p-4 sm:p-5">
          <h3 className="font-medium text-lg">LatentGEO.ai Assistant</h3>
          <p className="text-sm text-muted-foreground mt-1">
            Personalize your audit in seconds.
          </p>
        </div>

        <div
          ref={messagesContainerRef}
          className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-4"
        >
          {messages.map((msg, idx) => (
            <div
              key={idx}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[86%] sm:max-w-[82%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                  msg.role === "user"
                    ? "bg-brand text-brand-foreground"
                    : "bg-muted/60 text-foreground border border-border/60"
                }`}
              >
                <p className="whitespace-pre-wrap">{msg.content}</p>
                {msg.typing && (
                  <span className="inline-block w-1 h-4 bg-current ml-1 animate-pulse" />
                )}
              </div>
            </div>
          ))}
        </div>

        {step !== "done" && (
          <div className="border-t border-border/70 p-4 sm:p-5">
            <div className="flex gap-2">
              <Input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSend()}
                placeholder="Type your response..."
                disabled={isTyping}
                className="flex-1 bg-background min-h-[44px]"
              />
              <button
                onClick={handleSend}
                disabled={isTyping || !input.trim()}
                className="px-4 py-2 min-w-[48px] bg-brand text-brand-foreground rounded-lg hover:bg-brand/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                <Send className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
