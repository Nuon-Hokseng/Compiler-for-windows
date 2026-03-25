"use client";

import { useEffect, useState } from "react";
import { useI18n } from "@/contexts/I18nContext";
import { api, type CampaignResponse } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Folder, Trash2, Plus, ArrowRight, Loader2 } from "lucide-react";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";
import { toast } from "sonner";

export default function CampaignsPage() {
  const { t } = useI18n();
  const { user } = useAuth();
  const [campaigns, setCampaigns] = useState<CampaignResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);

  const [newName, setNewName] = useState("");
  const [newInterest, setNewInterest] = useState("");
  const [newKeywords, setNewKeywords] = useState("");
  const [newMax, setNewMax] = useState(50);

  useEffect(() => {
    if (!user) return;
    loadCampaigns();
  }, [user]);

  async function loadCampaigns() {
    setLoading(true);
    try {
      const data = await api.getCampaigns(user!.user_id);
      setCampaigns(data);
    } catch (err: any) {
      toast.error(err.message || "Failed to load campaigns");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!user) return;
    if (!newName.trim() || !newInterest.trim()) {
      toast.error("Please fill required fields");
      return;
    }
    setCreating(true);
    try {
      const optionalKeywords = newKeywords.split(",").map(k => k.trim()).filter(Boolean);
      await api.createCampaign({
        user_id: user.user_id,
        name: newName,
        target_interest: newInterest,
        optional_keywords: optionalKeywords.length > 0 ? optionalKeywords : undefined,
        max_profiles: newMax,
      });
      toast.success("Campaign created");
      setNewName("");
      setNewInterest("");
      setNewKeywords("");
      loadCampaigns();
    } catch (err: any) {
      toast.error(err.message || "Failed to create campaign");
    } finally {
      setCreating(false);
    }
  }

  async function handleDelete(id: number) {
    if (!confirm("Are you sure you want to delete this campaign? This will also un-link all leads associated with it.")) return;
    try {
      await api.deleteCampaign(id);
      toast.success("Campaign deleted");
      loadCampaigns();
    } catch (err: any) {
      toast.error(err.message || "Failed to delete campaign");
    }
  }

  return (
    <div className="space-y-6 max-w-6xl mx-auto py-8 px-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
          <Folder className="h-6 w-6" />
          {t("nav.campaigns") || "Campaigns"}
        </h1>
        <p className="text-muted-foreground mt-1">Manage and run targeted lead generation campaigns.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Plus className="h-5 w-5" />
            Create New Campaign
          </CardTitle>
          <CardDescription>Set up a reusable pipeline configuration</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label>Campaign Name *</Label>
                <Input value={newName} onChange={e => setNewName(e.target.value)} placeholder="e.g. Q1 Tech Recruitment" disabled={creating} />
              </div>
              <div className="space-y-2">
                <Label>Target Interest *</Label>
                <Input value={newInterest} onChange={e => setNewInterest(e.target.value)} placeholder="e.g. Software engineers in Tokyo" disabled={creating} />
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label>Optional Keywords (comma-separated)</Label>
                <Input value={newKeywords} onChange={e => setNewKeywords(e.target.value)} placeholder="react, typescript, ruby" disabled={creating} />
              </div>
              <div className="space-y-2">
                <Label>Max Profiles per Run</Label>
                <Input type="number" min={1} max={500} value={newMax} onChange={e => setNewMax(Number(e.target.value))} disabled={creating} />
              </div>
            </div>
            <Button type="submit" disabled={creating || !newName.trim() || !newInterest.trim()}>
              {creating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Create Campaign
            </Button>
          </form>
        </CardContent>
      </Card>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {loading && <p className="text-sm text-muted-foreground p-4">Loading campaigns...</p>}
        {!loading && campaigns.length === 0 && (
          <p className="text-sm text-muted-foreground p-4 col-span-full">No campaigns found. Create one above!</p>
        )}
        {campaigns.map(c => (
          <Card key={c.id} className="flex flex-col hover:border-primary/50 transition-colors">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg">{c.name}</CardTitle>
              <CardDescription className="line-clamp-2" title={c.target_interest}>
                Target: {c.target_interest}
              </CardDescription>
            </CardHeader>
            <CardContent className="flex-1 pb-2">
              <div className="text-xs text-muted-foreground space-y-1">
                <p>Max profiles/run: <span className="font-medium text-foreground">{c.max_profiles}</span></p>
                {c.optional_keywords && c.optional_keywords.length > 0 && (
                  <p className="truncate" title={c.optional_keywords.join(", ")}>
                    Keywords: {c.optional_keywords.join(", ")}
                  </p>
                )}
                <p>Created: {new Date(c.created_at).toLocaleDateString()}</p>
              </div>
            </CardContent>
            <CardFooter className="pt-2 flex justify-between border-t mt-2">
              <Button variant="ghost" size="sm" asChild className="text-primary hover:text-primary">
                <Link href={`/campaigns/${c.id}`} className="flex items-center gap-2">
                  Open Campaign <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
              <Button variant="ghost" size="icon" onClick={() => handleDelete(c.id)} className="text-destructive hover:bg-destructive/10 hover:text-destructive">
                <Trash2 className="h-4 w-4" />
              </Button>
            </CardFooter>
          </Card>
        ))}
      </div>
    </div>
  );
}
