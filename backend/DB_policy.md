-- ═══════════════════════════════════════════════════════════════════
-- RLS POLICIES for authentication + user_cookies
-- 
-- Since we use the ANON key (not user-level JWTs), we need to allow
-- the anon role full access. If you later add Supabase Auth with 
-- per-user JWTs, tighten these policies to use auth.uid().
-- ═══════════════════════════════════════════════════════════════════

-- ── authentication table ───────────────────────────────────────────

-- Enable RLS (idempotent — safe to re-run)
ALTER TABLE authentication ENABLE ROW LEVEL SECURITY;

-- Allow anon to INSERT (signup)
CREATE POLICY "anon_insert_authentication"
  ON authentication FOR INSERT
  TO anon
  WITH CHECK (true);

-- Allow anon to SELECT (login / lookup)
CREATE POLICY "anon_select_authentication"
  ON authentication FOR SELECT
  TO anon
  USING (true);

-- Allow anon to UPDATE (e.g. password change in future)
CREATE POLICY "anon_update_authentication"
  ON authentication FOR UPDATE
  TO anon
  USING (true)
  WITH CHECK (true);

-- Allow anon to DELETE (account deletion in future)
CREATE POLICY "anon_delete_authentication"
  ON authentication FOR DELETE
  TO anon
  USING (true);


-- ── user_cookies table ─────────────────────────────────────────────

ALTER TABLE user_cookies ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_insert_user_cookies"
  ON user_cookies FOR INSERT
  TO anon
  WITH CHECK (true);

CREATE POLICY "anon_select_user_cookies"
  ON user_cookies FOR SELECT
  TO anon
  USING (true);

CREATE POLICY "anon_update_user_cookies"
  ON user_cookies FOR UPDATE
  TO anon
  USING (true)
  WITH CHECK (true);

CREATE POLICY "anon_delete_user_cookies"
  ON user_cookies FOR DELETE
  TO anon
  USING (true);