"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Eye } from "lucide-react";

interface ApplicantItem {
  id: number;
  name: string;
  program: string;
  is_complete: boolean;
  created_at: string;
  outcome: string | null;
}

interface Assessment {
  outcome: string;
  rule_summary: string | null;
  transcript: string | null;
  created_at: string;
}

interface ApplicantDetail {
  id: number;
  name: string;
  program: string;
  details: Record<string, any> | null;
  is_complete: boolean;
  created_at: string;
  assessment: Assessment | null;
}

interface TranscriptMessage {
  role: string;
  content: string;
  created_at: string;
}

export default function ApplicantsPage() {
  const [applicants, setApplicants] = useState<ApplicantItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<ApplicantDetail | null>(null);
  const [transcript, setTranscript] = useState<TranscriptMessage[]>([]);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    apiFetch("/admin/applicants")
      .then((res) => res.json())
      .then((data) => setApplicants(data))
      .catch(() => setApplicants([]))
      .finally(() => setLoading(false));
  }, []);

  const openDetail = async (id: number) => {
    setSelectedId(id);
    setDetailLoading(true);
    try {
      const [detailRes, transcriptRes] = await Promise.all([
        apiFetch(`/admin/applicants/${id}`),
        apiFetch(`/admin/applicants/${id}/transcript`),
      ]);
      const detailData = await detailRes.json();
      const transcriptData = await transcriptRes.json();
      setDetail(detailData);
      setTranscript(transcriptData);
    } catch {
      setDetail(null);
      setTranscript([]);
    } finally {
      setDetailLoading(false);
    }
  };

  const outcomeBadge = (outcome: string | null) => {
    if (!outcome) return <Badge variant="outline">Pending</Badge>;
    if (outcome === "eligible") return <Badge className="bg-green-600 text-white hover:bg-green-700">Eligible</Badge>;
    if (outcome === "not_eligible") return <Badge variant="destructive">Not Eligible</Badge>;
    return <Badge variant="secondary">Needs Info</Badge>;
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Applicants</h2>
        <p className="text-muted-foreground">View and manage all admission interviews.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>All Applicants</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-sm text-muted-foreground">Loading...</p>
          ) : applicants.length === 0 ? (
            <p className="text-sm text-muted-foreground">No applicants yet.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Program</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead>Complete?</TableHead>
                  <TableHead>Outcome</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {applicants.map((a) => (
                  <TableRow key={a.id}>
                    <TableCell className="font-medium">{a.name}</TableCell>
                    <TableCell>{a.program}</TableCell>
                    <TableCell>{new Date(a.created_at).toLocaleDateString()}</TableCell>
                    <TableCell>{a.is_complete ? "Yes" : "No"}</TableCell>
                    <TableCell>{outcomeBadge(a.outcome)}</TableCell>
                    <TableCell className="text-right">
                      <Button size="sm" variant="ghost" onClick={() => openDetail(a.id)}>
                        <Eye className="h-4 w-4 mr-1" />
                        View
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Dialog open={selectedId !== null} onOpenChange={(open) => !open && setSelectedId(null)}>
        <DialogContent className="max-w-3xl max-h-[85vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle>Applicant Details</DialogTitle>
            <DialogDescription>
              {detail ? `${detail.name} — ${detail.program}` : "Loading..."}
            </DialogDescription>
          </DialogHeader>

          {detailLoading ? (
            <p className="text-sm text-muted-foreground py-4">Loading details...</p>
          ) : detail ? (
            <Tabs defaultValue="details" className="mt-2">
              <TabsList>
                <TabsTrigger value="details">Details</TabsTrigger>
                <TabsTrigger value="transcript">Transcript</TabsTrigger>
                <TabsTrigger value="assessment">Assessment</TabsTrigger>
              </TabsList>

              <TabsContent value="details" className="flex-1 overflow-auto">
                <div className="space-y-4 py-2">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-xs text-muted-foreground uppercase">Name</p>
                      <p className="text-sm font-medium">{detail.name}</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground uppercase">Program</p>
                      <p className="text-sm font-medium">{detail.program}</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground uppercase">Status</p>
                      <p className="text-sm font-medium">{detail.is_complete ? "Complete" : "In Progress"}</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground uppercase">Created</p>
                      <p className="text-sm font-medium">{new Date(detail.created_at).toLocaleString()}</p>
                    </div>
                  </div>
                  <Separator />
                  <div>
                    <p className="text-xs text-muted-foreground uppercase mb-2">Collected Details</p>
                    {detail.details && Object.keys(detail.details).length > 0 ? (
                      <pre className="text-xs bg-muted p-3 rounded-md overflow-auto">
                        {JSON.stringify(detail.details, null, 2)}
                      </pre>
                    ) : (
                      <p className="text-sm text-muted-foreground">No details collected yet.</p>
                    )}
                  </div>
                </div>
              </TabsContent>

              <TabsContent value="transcript" className="mt-2">
                <ScrollArea className="h-[400px] border rounded-md bg-white">
                  <div className="p-4 space-y-4">
                    {transcript.length === 0 ? (
                      <p className="text-sm text-muted-foreground">No messages.</p>
                    ) : (
                      transcript.map((msg, idx) => (
                        <div
                          key={idx}
                          className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                        >
                          <div className="max-w-[80%]">
                            <div
                              className={`rounded-2xl px-4 py-2 text-sm whitespace-pre-wrap ${
                                msg.role === "user"
                                  ? "bg-blue-600 text-white rounded-br-none"
                                  : "bg-slate-100 text-slate-800 rounded-bl-none"
                              }`}
                            >
                              {msg.content}
                            </div>
                            <p className="text-[10px] text-muted-foreground mt-1 px-1">
                              {msg.role === "user" ? "User" : "Bot"} · {new Date(msg.created_at).toLocaleTimeString()}
                            </p>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </ScrollArea>
              </TabsContent>

              <TabsContent value="assessment" className="flex-1 overflow-auto">
                <div className="space-y-4 py-2">
                  {detail.assessment ? (
                    <>
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <p className="text-xs text-muted-foreground uppercase">Outcome</p>
                          <div className="mt-1">{outcomeBadge(detail.assessment.outcome)}</div>
                        </div>
                        <div>
                          <p className="text-xs text-muted-foreground uppercase">Evaluated At</p>
                          <p className="text-sm font-medium">{new Date(detail.assessment.created_at).toLocaleString()}</p>
                        </div>
                      </div>
                      <Separator />
                      <div>
                        <p className="text-xs text-muted-foreground uppercase mb-1">Summary</p>
                        <p className="text-sm">{detail.assessment.rule_summary || "—"}</p>
                      </div>
                      <Separator />
                      <div>
                        <p className="text-xs text-muted-foreground uppercase mb-1">Transcript Snapshot</p>
                        <ScrollArea className="h-48 border rounded-md">
                          <pre className="text-xs p-3 whitespace-pre-wrap">
                            {detail.assessment.transcript || "—"}
                          </pre>
                        </ScrollArea>
                      </div>
                    </>
                  ) : (
                    <p className="text-sm text-muted-foreground">No assessment available.</p>
                  )}
                </div>
              </TabsContent>
            </Tabs>
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  );
}
