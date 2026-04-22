"use client";

import { useState, useEffect } from "react";
import ChatModal from "@/components/ChatModal";

interface InterviewItem {
  id: number;
  name: string;
  program: string;
  is_complete: boolean;
  created_at: string;
}

export default function Home() {
  const [isOpen, setIsOpen] = useState(false);
  const [applicantId, setApplicantId] = useState<number | null>(null);
  const [previousInterviews, setPreviousInterviews] = useState<InterviewItem[]>([]);
  const [showSelector, setShowSelector] = useState(false);

  // Load previous interview IDs from localStorage on mount
  useEffect(() => {
    const raw = localStorage.getItem("falcon_interview_ids");
    if (raw) {
      try {
        const ids: number[] = JSON.parse(raw);
        fetchStatuses(ids);
      } catch {
        localStorage.removeItem("falcon_interview_ids");
      }
    }
  }, []);

  const fetchStatuses = async (ids: number[]) => {
    const results: InterviewItem[] = [];
    for (const id of ids) {
      try {
        const res = await fetch(`/api/interview/${id}/status`);
        if (res.ok) {
          const data = await res.json();
          results.push(data);
        }
      } catch {
        // ignore stale IDs
      }
    }
    setPreviousInterviews(results);
  };

  const addInterviewId = (id: number) => {
    const raw = localStorage.getItem("falcon_interview_ids");
    const ids: number[] = raw ? JSON.parse(raw) : [];
    if (!ids.includes(id)) {
      ids.push(id);
      localStorage.setItem("falcon_interview_ids", JSON.stringify(ids));
    }
  };

  const handleStartClick = () => {
    if (previousInterviews.length > 0) {
      setShowSelector(true);
    } else {
      startNewInterview();
    }
  };

  const startNewInterview = async () => {
    try {
      const res = await fetch("/api/interview/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      const data = await res.json();
      setApplicantId(data.applicant_id);
      addInterviewId(data.applicant_id);
      setIsOpen(true);
      setShowSelector(false);
      // Refresh previous interviews list
      const raw = localStorage.getItem("falcon_interview_ids");
      if (raw) fetchStatuses(JSON.parse(raw));
    } catch {
      alert("Failed to start interview. Please try again.");
    }
  };

  const resumeInterview = (id: number) => {
    setApplicantId(id);
    setIsOpen(true);
    setShowSelector(false);
  };

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
          onClick={handleStartClick}
          className="inline-flex items-center justify-center rounded-xl bg-blue-600 px-8 py-3 text-lg font-semibold text-white shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition"
        >
          Start Interview
        </button>
      </div>

      {/* Resume / New selector overlay */}
      {showSelector && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
            <h2 className="mb-4 text-xl font-semibold text-slate-900">
              Welcome back!
            </h2>
            <p className="mb-4 text-slate-600">
              You have previous interviews. Would you like to resume one or start fresh?
            </p>

            <div className="mb-4 max-h-48 overflow-y-auto space-y-2">
              {previousInterviews.map((iv) => (
                <button
                  key={iv.id}
                  onClick={() => resumeInterview(iv.id)}
                  className="w-full rounded-lg border border-slate-200 p-3 text-left hover:bg-slate-50"
                >
                  <div className="font-medium text-slate-900">
                    {iv.name} — {iv.program}
                  </div>
                  <div className="text-xs text-slate-500">
                    {iv.is_complete ? "Completed" : "In progress"} · {new Date(iv.created_at).toLocaleDateString()}
                  </div>
                </button>
              ))}
            </div>

            <button
              onClick={startNewInterview}
              className="w-full rounded-lg bg-blue-600 px-4 py-3 text-sm font-semibold text-white hover:bg-blue-700"
            >
              Start a new interview
            </button>

            <button
              onClick={() => setShowSelector(false)}
              className="mt-2 w-full rounded-lg px-4 py-2 text-sm text-slate-500 hover:text-slate-700"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      <ChatModal
        isOpen={isOpen}
        onClose={() => {
          setIsOpen(false);
          setApplicantId(null);
          // Refresh list after closing
          const raw = localStorage.getItem("falcon_interview_ids");
          if (raw) fetchStatuses(JSON.parse(raw));
        }}
        applicantId={applicantId}
      />
    </main>
  );
}
