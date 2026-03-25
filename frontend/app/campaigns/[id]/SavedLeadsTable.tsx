"use client";

import { useEffect, useState } from "react";
import { api, type SavedLead } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { Loader2, Trash2, Users } from "lucide-react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

export function SavedLeadsTable({ campaignId }: { campaignId: number }) {
  const { user } = useAuth();
  const [leads, setLeads] = useState<SavedLead[]>([]);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  useEffect(() => {
    if (!user) return;
    loadLeads();

    const handleReload = () => loadLeads();
    window.addEventListener("reload-campaign-leads", handleReload);
    return () => window.removeEventListener("reload-campaign-leads", handleReload);
  }, [user, campaignId]);

  async function loadLeads() {
    setLoading(true);
    try {
      const res = await api.getSavedLeads(user!.user_id, undefined, undefined, campaignId);
      setLeads(res.leads || []);
    } catch (err) {
      toast.error("Failed to load campaign leads");
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete(leadId: number) {
    setDeletingId(leadId);
    try {
      await api.deleteSavedLead(leadId);
      setLeads(prev => prev.filter(l => l.id !== leadId));
      toast.success("Lead removed");
    } catch (err) {
      toast.error("Failed to remove lead");
    } finally {
      setDeletingId(null);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (leads.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        <Users className="h-10 w-10 mx-auto mb-2 opacity-50" />
        <p className="text-sm">No leads discovered yet.</p>
        <p className="text-xs mt-1">Run the campaign pipeline to populate this list.</p>
      </div>
    );
  }

  return (
    <div className="rounded-md border overflow-auto max-h-[600px]">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Username</TableHead>
            <TableHead>Target</TableHead>
            <TableHead className="text-center">Score</TableHead>
            <TableHead className="text-center">Followers</TableHead>
            <TableHead className="w-10"></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {leads.map((lead) => (
            <TableRow key={lead.id}>
              <TableCell className="font-medium">
                <a href={`https://instagram.com/${lead.username}`} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                  @{lead.username}
                </a>
              </TableCell>
              <TableCell className="text-muted-foreground">{lead.niche}</TableCell>
              <TableCell className="text-center font-semibold">{lead.total_score}</TableCell>
              <TableCell className="text-center text-muted-foreground">{lead.followers_count.toLocaleString()}</TableCell>
              <TableCell>
                <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive" onClick={() => handleDelete(lead.id)} disabled={deletingId === lead.id}>
                  {deletingId === lead.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
