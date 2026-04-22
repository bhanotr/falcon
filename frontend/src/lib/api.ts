const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function apiFetch(path: string, options: RequestInit = {}) {
  const token = typeof window !== "undefined" ? localStorage.getItem("admin_token") : null;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });
  if (res.status === 401) {
    localStorage.removeItem("admin_token");
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
  }
  return res;
}
