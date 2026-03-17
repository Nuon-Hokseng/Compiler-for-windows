"use client";

import { Suspense, useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { api, type CookieSnapshot } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { useSession, useCookies } from "@/lib/swr";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AccountsPageHeader } from "../../components/dashboard/accounts/AccountsPageHeader";
import { AccountsTable } from "../../components/dashboard/accounts/AccountsTable";
import { AddAccountDialog } from "../../components/dashboard/accounts/AddAccountDialog";
import { DeleteAccountDialog } from "../../components/dashboard/accounts/DeleteAccountDialog";

// 1. Top-level page component wrapped in Suspense
export default function AccountsPage() {
  return (
    <Suspense fallback={<AccountsPageFallback />}>
      <AccountsPageContent />
    </Suspense>
  );
}

function AccountsPageFallback() {
  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Accounts</h1>
        <p className="text-muted-foreground">Loading...</p>
      </div>
    </div>
  );
}

// 2. Actual content component that uses useSearchParams
function AccountsPageContent() {
  const { user, isLoading: authLoading } = useAuth();
  const searchParams = useSearchParams();
  const [addOpen, setAddOpen] = useState(false);

  useEffect(() => {
    if (searchParams.get("add") === "1") {
      setAddOpen(true);
    }
  }, [searchParams]);

  // SWR hooks
  const {
    data: session,
    isLoading: sessionLoading,
    mutate: mutateSession,
  } = useSession(user?.user_id);

  const {
    data: cookiesData,
    isLoading: cookiesLoading,
    mutate: mutateCookies,
  } = useCookies(user?.user_id, false);

  const loading = sessionLoading || cookiesLoading;
  const hasCookies = session?.has_cookies ?? false;
  const instagramUsername = session?.instagram_username ?? null;

  // Normalise cookies to always be an array
  const cookieSnapshots: CookieSnapshot[] = cookiesData
    ? Array.isArray(cookiesData.cookies)
      ? cookiesData.cookies
      : cookiesData.cookies
        ? [cookiesData.cookies]
        : []
    : [];

  // Delete dialog state
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<{
    id: number;
    label: string;
  } | null>(null);
  const [deleting, setDeleting] = useState(false);

  function handleRefresh() {
    mutateSession();
    mutateCookies();
  }

  function handleDeleteClick(cookieId: number, label: string) {
    setDeleteTarget({ id: cookieId, label });
    setDeleteOpen(true);
  }

  async function handleDeleteConfirm(cookieId: number) {
    setDeleting(true);
    try {
      await api.deleteCookie(cookieId);
      toast.success("Session removed successfully");
      setDeleteOpen(false);
      setDeleteTarget(null);
      mutateSession();
      mutateCookies();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to delete session");
    } finally {
      setDeleting(false);
    }
  }

  function handleAddSuccess() {
    mutateSession();
    mutateCookies();
  }

  if (authLoading || !user) {
    return (
      <div className="space-y-6 max-w-5xl">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Accounts</h1>
          <p className="text-muted-foreground">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-5xl">
      <AccountsPageHeader
        loading={loading}
        onRefresh={handleRefresh}
        onAddClick={() => setAddOpen(true)}
      />

      <AccountsTable
        hasCookies={hasCookies}
        instagramUsername={instagramUsername}
        loading={loading}
        onAddClick={() => setAddOpen(true)}
        cookieSnapshots={cookieSnapshots}
        onDeleteCookie={handleDeleteClick}
      />

      <AddAccountDialog
        open={addOpen}
        onOpenChange={setAddOpen}
        onSuccess={handleAddSuccess}
        userId={user.user_id}
      />

      <DeleteAccountDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        cookieId={deleteTarget?.id ?? null}
        label={deleteTarget?.label ?? null}
        onConfirm={handleDeleteConfirm}
        deleting={deleting}
      />
    </div>
  );
}
