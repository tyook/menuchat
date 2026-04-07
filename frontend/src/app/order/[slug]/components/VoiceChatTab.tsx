"use client";

import { useState } from "react";
import { Send, Check } from "lucide-react";
import { Textarea } from "@/components/ui/textarea";
import { useOrderStore } from "@/stores/order-store";
import { usePreferencesStore } from "@/stores/preferences-store";
import { useSpeechRecognition } from "@/hooks/use-speech-recognition";
import { useParseOrder } from "@/hooks/use-parse-order";
import { SPEECH_LANGUAGES } from "@/lib/constants";

interface VoiceChatTabProps {
  slug: string;
}

export function VoiceChatTab({ slug }: VoiceChatTabProps) {
  const { setRawInput } = useOrderStore();
  const { preferredLanguage } = usePreferencesStore();
  const [input, setInput] = useState("");
  const [speechLang, setSpeechLang] = useState(preferredLanguage);
  const [addedMessage, setAddedMessage] = useState<string | null>(null);
  const { isListening, transcript, startListening, stopListening, isSupported } =
    useSpeechRecognition({ lang: speechLang || undefined });

  const parseOrderMutation = useParseOrder(slug);

  const currentInput = isListening ? transcript : input;

  const handleSubmit = async () => {
    const text = currentInput.trim();
    if (!text || parseOrderMutation.isPending) return;

    setRawInput(text);
    setInput("");

    parseOrderMutation.mutate(text, {
      onSuccess: (result) => {
        const count = result.items.reduce((sum, i) => sum + i.quantity, 0);
        const names = result.items.map((i) => `${i.quantity}x ${i.name}`).join(", ");
        setAddedMessage(`Added ${names} (${count} item${count !== 1 ? "s" : ""})`);
        setTimeout(() => setAddedMessage(null), 3000);
      },
    });
  };

  const toggleVoice = () => {
    if (isListening) {
      stopListening();
      setInput(transcript);
    } else {
      startListening();
    }
  };

  const waveHeights = [28, 36, 24, 40, 32, 20, 38, 26, 34, 22, 30, 40, 24, 36, 28, 32];

  return (
    <div className="flex flex-col items-center gap-8 px-4 py-10 pb-24">
      {/* Header */}
      <div className="text-center animate-fade-in-up">
        <h2 className="text-2xl font-semibold tracking-tight mb-2">What would you like?</h2>
        <p className="text-sm text-muted-foreground">
          Speak or type your order naturally
        </p>
      </div>

      {/* Microphone orb section */}
      {isSupported && (
        <div className="relative flex flex-col items-center gap-4 animate-fade-in-up-delay-1">
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-[55%] w-[300px] h-[300px] bg-[radial-gradient(circle,rgba(124,58,237,0.2),rgba(99,102,241,0.08)_50%,transparent_70%)] rounded-full pointer-events-none" />

          {isListening && (
            <p className="text-[11px] uppercase tracking-[3px] text-muted-foreground animate-fade-in-up">
              Listening...
            </p>
          )}

          <div className="relative flex items-center justify-center">
            {isListening && (
              <>
                <div
                  className="absolute top-1/2 left-1/2 border border-primary/15 rounded-full animate-pulse-ring"
                  style={{ width: 160, height: 160 }}
                />
                <div
                  className="absolute top-1/2 left-1/2 border border-primary/15 rounded-full animate-pulse-ring-delayed"
                  style={{ width: 200, height: 200 }}
                />
              </>
            )}

            <button
              onClick={toggleVoice}
              disabled={parseOrderMutation.isPending}
              className="relative w-[120px] h-[120px] rounded-full flex items-center justify-center gradient-primary glow-primary-lg transition-all duration-300 hover:scale-105 active:scale-95 focus:outline-none focus:ring-2 focus:ring-primary/50 focus:ring-offset-2 focus:ring-offset-background disabled:opacity-50"
              aria-label={isListening ? "Stop recording" : "Start recording"}
            >
              {isListening ? (
                <div className="flex items-center gap-[3px]">
                  {waveHeights.map((h, i) => (
                    <div
                      key={i}
                      className="w-[3px] rounded-full bg-primary-foreground/80 animate-waveform"
                      style={
                        {
                          "--wave-height": `${h}px`,
                          animationDelay: `${i * 0.075}s`,
                          height: "12px",
                        } as React.CSSProperties
                      }
                    />
                  ))}
                </div>
              ) : (
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="40"
                  height="40"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.75"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="text-primary-foreground"
                >
                  <path d="M12 2a3 3 0 0 1 3 3v7a3 3 0 0 1-6 0V5a3 3 0 0 1 3-3Z" />
                  <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                  <line x1="12" x2="12" y1="19" y2="22" />
                </svg>
              )}
            </button>
          </div>

          <select
            value={speechLang}
            onChange={(e) => setSpeechLang(e.target.value)}
            disabled={isListening || parseOrderMutation.isPending}
            className="rounded-md border border-input bg-background px-3 py-1.5 text-xs text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary/50 disabled:opacity-50"
          >
            {SPEECH_LANGUAGES.map((lang) => (
              <option key={lang.code} value={lang.code}>
                {lang.label}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Live transcript display */}
      {isListening && (
        <div className="w-full glass-card rounded-2xl p-4 min-h-[80px] animate-fade-in-up">
          <p className="text-foreground/70 text-sm leading-relaxed">
            {transcript || (
              <span className="text-muted-foreground italic">Start speaking…</span>
            )}
            <span className="w-0.5 h-4 bg-primary/70 animate-blink-cursor inline-block ml-1 align-middle" />
          </p>
        </div>
      )}

      {/* Inline loading indicator */}
      {parseOrderMutation.isPending && (
        <div className="w-full glass-card rounded-2xl p-4 animate-fade-in-up">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-primary/50 animate-pulse" style={{ animationDelay: "0s" }} />
              <span className="w-2 h-2 rounded-full bg-primary/50 animate-pulse" style={{ animationDelay: "0.2s" }} />
              <span className="w-2 h-2 rounded-full bg-primary/50 animate-pulse" style={{ animationDelay: "0.4s" }} />
            </div>
            <p className="text-sm text-muted-foreground">Understanding your order...</p>
          </div>
        </div>
      )}

      {/* Success confirmation */}
      {addedMessage && (
        <div className="w-full glass-card rounded-2xl p-4 animate-fade-in-up border border-green-500/20 bg-green-500/5">
          <div className="flex items-center gap-2">
            <Check className="h-4 w-4 text-green-500 shrink-0" />
            <p className="text-sm text-green-400">{addedMessage}</p>
          </div>
        </div>
      )}

      {/* Text input */}
      {!isListening && (
        <div className="w-full animate-fade-in-up-delay-2">
          <div className="glass-card rounded-xl p-1 flex items-end gap-2">
            <Textarea
              value={currentInput}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Or type your order here…"
              rows={3}
              disabled={isListening || parseOrderMutation.isPending}
              className="flex-1 resize-none border-0 bg-transparent focus-visible:ring-0 focus-visible:ring-offset-0 text-sm placeholder:text-muted-foreground/60 disabled:opacity-50"
            />
            <button
              onClick={handleSubmit}
              disabled={!currentInput.trim() || parseOrderMutation.isPending}
              className="mb-1 mr-1 p-2.5 bg-primary/20 rounded-lg text-primary hover:bg-primary/30 transition-colors disabled:opacity-40 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-primary/50"
              aria-label="Submit order"
            >
              <Send size={18} />
            </button>
          </div>
        </div>
      )}

      {/* Error display */}
      {parseOrderMutation.isError && (
        <p className="text-destructive text-sm">
          {parseOrderMutation.error instanceof Error
            ? parseOrderMutation.error.message
            : "Failed to parse order"}
        </p>
      )}
    </div>
  );
}
