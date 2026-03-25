"use client";

import { useEffect, useState } from "react";
import { useI18n } from "@/contexts/I18nContext";
import { api, type CampaignResponse } from "@/lib/api";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
  CardFooter,
} from "@/components/ui/card";
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
      toast.error(err.message || t("campaigns.toasts.loadFailed"));
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!user) return;
    if (!newName.trim() || !newInterest.trim()) {
      toast.error(t("campaigns.toasts.fillRequired"));
      return;
    }
    setCreating(true);
    try {
      const optionalKeywords = newKeywords
        .split(",")
        .map((k) => k.trim())
        .filter(Boolean);
      await api.createCampaign({
        user_id: user.user_id,
        name: newName,
        target_interest: newInterest,
        optional_keywords:
          optionalKeywords.length > 0 ? optionalKeywords : undefined,
        max_profiles: newMax,
      });
      toast.success(t("campaigns.toasts.created"));
      setNewName("");
      setNewInterest("");
      setNewKeywords("");
      loadCampaigns();
    } catch (err: any) {
      toast.error(err.message || t("campaigns.toasts.createFailed"));
    } finally {
      setCreating(false);
    }
  }

  async function handleDelete(id: number) {
    if (!confirm(t("campaigns.delete.confirm"))) return;
    try {
      await api.deleteCampaign(id);
      toast.success(t("campaigns.toasts.deleted"));
      loadCampaigns();
    } catch (err: any) {
      toast.error(err.message || t("campaigns.toasts.deleteFailed"));
    }
  }

  return (
    <div className="space-y-6 max-w-6xl mx-auto py-8 px-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
          <Folder className="h-6 w-6" />
          {t("nav.campaigns")}
        </h1>
        <p className="text-muted-foreground mt-1">
          {t("campaigns.page.subtitle")}
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Plus className="h-5 w-5" />
            {t("campaigns.create.title")}
          </CardTitle>
          <CardDescription>{t("campaigns.create.description")}</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label>{t("campaigns.form.name")}</Label>
                <Input
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder={t("campaigns.form.namePlaceholder")}
                  disabled={creating}
                />
              </div>
              <div className="space-y-2">
                <Label>{t("campaigns.form.interest")}</Label>
                <Input
                  value={newInterest}
                  onChange={(e) => setNewInterest(e.target.value)}
                  placeholder={t("campaigns.form.interestPlaceholder")}
                  disabled={creating}
                />
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label>{t("campaigns.form.keywords")}</Label>
                <Input
                  value={newKeywords}
                  onChange={(e) => setNewKeywords(e.target.value)}
                  placeholder={t("campaigns.form.keywordsPlaceholder")}
                  disabled={creating}
                />
              </div>
              <div className="space-y-2">
                <Label>{t("campaigns.form.maxProfiles")}</Label>
                <Input
                  type="number"
                  min={1}
                  max={500}
                  value={newMax}
                  onChange={(e) => setNewMax(Number(e.target.value))}
                  disabled={creating}
                />
              </div>
            </div>
            <Button
              type="submit"
              disabled={creating || !newName.trim() || !newInterest.trim()}>
              {creating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {t("campaigns.create.submit")}
            </Button>
          </form>
        </CardContent>
      </Card>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {loading && (
          <p className="text-sm text-muted-foreground p-4">
            {t("campaigns.list.loading")}
          </p>
        )}
        {!loading && campaigns.length === 0 && (
          <p className="text-sm text-muted-foreground p-4 col-span-full">
            {t("campaigns.list.empty")}
          </p>
        )}
        {campaigns.map((c) => (
          <Card
            key={c.id}
            className="flex flex-col hover:border-primary/50 transition-colors">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg">{c.name}</CardTitle>
              <CardDescription
                className="line-clamp-2"
                title={c.target_interest}>
                {t("campaigns.card.target")}: {c.target_interest}
              </CardDescription>
            </CardHeader>
            <CardContent className="flex-1 pb-2">
              <div className="text-xs text-muted-foreground space-y-1">
                <p>
                  {t("campaigns.card.maxProfiles")}:{" "}
                  <span className="font-medium text-foreground">
                    {c.max_profiles}
                  </span>
                </p>
                {c.optional_keywords && c.optional_keywords.length > 0 && (
                  <p
                    className="truncate"
                    title={c.optional_keywords.join(", ")}>
                    {t("campaigns.card.keywords")}:{" "}
                    {c.optional_keywords.join(", ")}
                  </p>
                )}
                <p>
                  {t("campaigns.card.created")}:{" "}
                  {new Date(c.created_at).toLocaleDateString()}
                </p>
              </div>
            </CardContent>
            <CardFooter className="pt-2 flex justify-between border-t mt-2">
              <Button
                variant="ghost"
                size="sm"
                asChild
                className="text-primary hover:text-primary">
                <Link
                  href={`/campaigns/${c.id}`}
                  className="flex items-center gap-2">
                  {t("campaigns.card.open")} <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => handleDelete(c.id)}
                className="text-destructive hover:bg-destructive/10 hover:text-destructive">
                <Trash2 className="h-4 w-4" />
              </Button>
            </CardFooter>
          </Card>
        ))}
      </div>
    </div>
  );
}
