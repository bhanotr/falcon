"use client";

import { useState, useRef, useEffect } from "react";

interface Message {
  role: "user" | "bot";
  content: string;
}

export default function ChatModal({
  isOpen,
  onClose,
  applicantId,
}: {
  isOpen: boolean;
  onClose: () => void;
  applicantId: number | null;
}) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  // Load chat history when modal opens with a valid applicantId
  useEffect(() => {
    if (isOpen && applicantId) {
      setIsComplete(false);
      fetch(`http://localhost:8000/interview/${applicantId}/messages`)
        .then((res) => {
          if (!res.ok) throw new Error("Failed to load messages");
          return res.json();
        })
        .then((data: { role: string; content: string }[]) => {
          const loaded: Message[] = data.map((m) => ({
            role: m.role === "user" ? "user" : "bot",
            content: m.content,
          }));
          setMessages(loaded);
        })
        .catch(() => {
          setMessages([
            {
              role: "bot",
              content:
                "Hello! Welcome to Falcon University Admission Pre-Assessment. Let's get started — what is your full name?",
            },
          ]);
        });
    } else if (!isOpen) {
      setMessages([]);
      setInput("");
      setLoading(false);
      setIsComplete(false);
    }
  }, [isOpen, applicantId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || loading || !applicantId || isComplete) return;

    const userMsg: Message = { role: "user", content: text };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch(
        `http://localhost:8000/interview/${applicantId}/chat`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: text }),
        }
      );

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }

      const data = await res.json();
      const botMsg: Message = {
        role: "bot",
        content: data.response || "...",
      };
      setMessages((prev) => [...prev, botMsg]);

      if (data.interview_complete) {
        setIsComplete(true);
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: "bot",
          content: "Sorry, something went wrong. Please try again later.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4">
      <div className="flex w-full max-w-xl flex-col rounded-2xl bg-white shadow-2xl max-h-[80vh]">
        {/* Header */}
        <div className="flex items-center justify-between border-b px-6 py-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">
              Admission Interview
            </h2>
            {applicantId && (
              <p className="text-xs text-slate-500">ID: {applicantId}</p>
            )}
          </div>
          <button
            onClick={onClose}
            className="rounded-md p-1 text-slate-500 hover:bg-slate-100 hover:text-slate-700"
            aria-label="Close"
          >
            <svg
              className="h-5 w-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {messages.map((msg, idx) => (
            <div
              key={idx}
              className={`flex ${
                msg.role === "user" ? "justify-end" : "justify-start"
              }`}
            >
              <div
                className={`max-w-[75%] rounded-2xl px-4 py-2 text-sm whitespace-pre-wrap ${
                  msg.role === "user"
                    ? "bg-blue-600 text-white rounded-br-none"
                    : "bg-slate-100 text-slate-800 rounded-bl-none"
                }`}
              >
                {msg.content}
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex justify-start">
              <div className="max-w-[75%] rounded-2xl rounded-bl-none bg-slate-100 px-4 py-2 text-sm text-slate-500">
                Thinking...
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Completion banner */}
        {isComplete && (
          <div className="border-t bg-green-50 px-6 py-3">
            <p className="text-sm font-medium text-green-800">
              Interview complete! Your application has been evaluated.
            </p>
          </div>
        )}

        {/* Input */}
        <div className="border-t px-6 py-4">
          <div className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && sendMessage()}
              placeholder={
                isComplete
                  ? "Interview finished"
                  : "Type your message..."
              }
              disabled={isComplete || loading}
              className="flex-1 rounded-lg border border-slate-300 px-4 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-slate-100 disabled:text-slate-500"
            />
            <button
              onClick={sendMessage}
              disabled={loading || !input.trim() || isComplete}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Send
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
