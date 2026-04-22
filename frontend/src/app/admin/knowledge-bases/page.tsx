"use client";

import { useEffect, useRef, useState } from "react";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ToggleLeft, ToggleRight, Upload } from "lucide-react";

interface DocumentItem {
  id: number;
  filename: string;
  uploaded_at: string;
  is_active: boolean;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function KnowledgeBasesPage() {
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchDocs = async () => {
    setLoading(true);
    try {
      const res = await apiFetch("/admin/documents");
      const data = await res.json();
      setDocs(data);
    } catch {
      setDocs([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDocs();
  }, []);

  const toggleDoc = async (id: number) => {
    try {
      const res = await apiFetch(`/admin/documents/${id}/toggle`, { method: "PATCH" });
      if (res.ok) {
        await fetchDocs();
      }
    } catch {
      // ignore
    }
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setUploadStatus("Only PDF files are accepted.");
      return;
    }

    setUploading(true);
    setUploadStatus(null);

    const token = localStorage.getItem("admin_token");
    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(`${API_BASE}/documents/upload`, {
        method: "POST",
        headers: {
          Authorization: token ? `Bearer ${token}` : "",
        },
        body: formData,
      });
      if (res.ok) {
        setUploadStatus(`Uploaded ${file.name} successfully.`);
        await fetchDocs();
      } else {
        const data = await res.json().catch(() => ({}));
        setUploadStatus(data.detail || "Upload failed.");
      }
    } catch {
      setUploadStatus("Upload failed.");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Knowledge Bases</h2>
        <p className="text-muted-foreground">
          Manage uploaded documents. Inactive documents are excluded from the interview bot's knowledge base.
        </p>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Documents</CardTitle>
          <div className="flex items-center gap-3">
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf"
              className="hidden"
              onChange={handleFileChange}
            />
            <Button
              size="sm"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
            >
              <Upload className="h-4 w-4 mr-1" />
              {uploading ? "Uploading..." : "Upload PDF"}
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {uploadStatus && (
            <p className={`text-sm mb-4 ${uploadStatus.includes("successfully") ? "text-green-700" : "text-red-600"}`}>
              {uploadStatus}
            </p>
          )}
          {loading ? (
            <p className="text-sm text-muted-foreground">Loading...</p>
          ) : docs.length === 0 ? (
            <p className="text-sm text-muted-foreground">No documents uploaded yet.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Filename</TableHead>
                  <TableHead>Uploaded</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {docs.map((doc) => (
                  <TableRow key={doc.id}>
                    <TableCell className="font-medium">{doc.filename}</TableCell>
                    <TableCell>{new Date(doc.uploaded_at).toLocaleDateString()}</TableCell>
                    <TableCell>
                      {doc.is_active ? (
                        <Badge className="bg-green-600 text-white hover:bg-green-700">Active</Badge>
                      ) : (
                        <Badge variant="secondary">Inactive</Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button size="sm" variant="ghost" onClick={() => toggleDoc(doc.id)}>
                        {doc.is_active ? (
                          <>
                            <ToggleRight className="h-4 w-4 mr-1 text-green-600" />
                            Deactivate
                          </>
                        ) : (
                          <>
                            <ToggleLeft className="h-4 w-4 mr-1 text-slate-500" />
                            Activate
                          </>
                        )}
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
