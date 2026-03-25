"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { api, type CampaignResponse, type LeadGenResult } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Loader2, PlayCircle, Users } from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";
import { LeadGenForm } from "@/components/dashboard/leads/LeadGenForm";
import { SavedLeadsTable } from "./SavedLeadsTable";

export default function CampaignDetailPage() {
  const { id } = useParams() as { id: string };
  const { user } = useAuth();
  
  const [campaign, setCampaign] = useState<CampaignResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user || !id) return;
    loadCampaign();
  }, [user, id]);

  async function loadCampaign() {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getCampaignById(Number(id));
      if (data.user_id !== user?.user_id) {
        throw new Error("Unauthorized");
      }
      setCampaign(data);
    } catch (err: any) {
      setError(err.message || "Failed to load campaign");
      toast.error("Failed to load campaign");
    } finally {
      setLoading(false);
    }
  }

  function handlePipelineResult(result: LeadGenResult) {
    // After running the pipeline, we reload the leads table
    window.dispatchEvent(new CustomEvent("reload-campaign-leads"));
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error || !campaign) {
    return (
      <div className="p-8 text-center space-y-4">
        <p className="text-destructive">{error || "Campaign not found"}</p>
        <Button asChild variant="outline">
          <Link href="/campaigns">Back to Campaigns</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-6xl mx-auto py-8 lg:px-4">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild className="shrink-0">
          <Link href="/campaigns">
            <ArrowLeft className="h-5 w-5" />
          </Link>
        </Button>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{campaign.name}</h1>
          <p className="text-muted-foreground flex items-center gap-2">
            Target: <span className="font-medium text-foreground">{campaign.target_interest}</span>
          </p>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <PlayCircle className="h-5 w-5" />
                Run Campaign
              </CardTitle>
              <CardDescription>
                Execute the AI lead generation pipeline for this campaign.
                All discovered and qualified leads will be automatically linked.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <LeadGenForm 
                onResults={handlePipelineResult}
                campaignId={campaign.id}
                fixedTargetInterest={campaign.target_interest}
                fixedKeywords={campaign.optional_keywords?.join(", ") || ""}
                fixedMaxProfiles={campaign.max_profiles}
              />
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card className="h-full flex flex-col">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Users className="h-5 w-5" />
                Campaign Leads
              </CardTitle>
              <CardDescription>
                Qualified leads collected across all pipeline runs for this campaign.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex-1">
              <SavedLeadsTable campaignId={campaign.id} />
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
