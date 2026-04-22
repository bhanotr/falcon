"use client";

import { useState } from "react";
import ChatModal from "@/components/ChatModal";

export default function Home() {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-4">
      <div className="text-center space-y-6 max-w-lg">
        <h1 className="text-4xl font-bold tracking-tight text-slate-900">
          Falcon University
        </h1>
        <p className="text-lg text-slate-600">
          Welcome to the Admission Pre-Assessment.
        </p>
        <button
          onClick={() => setIsOpen(true)}
          className="inline-flex items-center justify-center rounded-xl bg-blue-600 px-8 py-3 text-lg font-semibold text-white shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition"
        >
          Start Interview
        </button>
      </div>

      <ChatModal isOpen={isOpen} onClose={() => setIsOpen(false)} />
    </main>
  );
}
