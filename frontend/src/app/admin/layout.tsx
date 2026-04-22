"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Users, BookOpen, LogOut } from "lucide-react";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("admin_token");
    if (!token) {
      router.replace("/login");
      return;
    }
    apiFetch("/auth/me")
      .then((res) => {
        if (!res.ok) throw new Error("Unauthorized");
        return res.json();
      })
      .then((user) => {
        if (!user.is_admin) throw new Error("Not admin");
        setChecking(false);
      })
      .catch(() => {
        localStorage.removeItem("admin_token");
        router.replace("/login");
      });
  }, [router]);

  const logout = () => {
    localStorage.removeItem("admin_token");
    router.replace("/login");
  };

  const nav = [
    { label: "Applicants", href: "/admin/applicants", icon: Users },
    { label: "Knowledge Bases", href: "/admin/knowledge-bases", icon: BookOpen },
  ];

  if (checking) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <p className="text-slate-500">Checking access...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex bg-slate-50">
      {/* Sidebar */}
      <aside className="w-64 border-r bg-white flex flex-col">
        <div className="px-6 py-5">
          <h1 className="text-lg font-bold text-slate-900">Falcon Admin</h1>
        </div>
        <Separator />
        <nav className="flex-1 px-4 py-4 space-y-1">
          {nav.map((item) => {
            const active = pathname === item.href;
            return (
              <button
                key={item.href}
                onClick={() => router.push(item.href)}
                className={`w-full flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
                  active
                    ? "bg-slate-900 text-white"
                    : "text-slate-700 hover:bg-slate-100"
                }`}
              >
                <item.icon className="h-4 w-4" />
                {item.label}
              </button>
            );
          })}
        </nav>
        <div className="p-4">
          <Button variant="outline" className="w-full gap-2" onClick={logout}>
            <LogOut className="h-4 w-4" />
            Log out
          </Button>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 p-8 overflow-auto">{children}</main>
    </div>
  );
}
