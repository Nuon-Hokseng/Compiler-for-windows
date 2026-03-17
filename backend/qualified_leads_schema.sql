-- ═══════════════════════════════════════════════════════════════════
-- qualified_leads table — stores users that passed the AI qualification
-- stage, linked to the Instagram account (cookie_id) and niche.
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS qualified_leads (
    id              BIGSERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL,           -- web-app user (authentication.id)
    cookie_id       INTEGER NOT NULL,           -- which IG account was used (user_cookies.id)
    niche           TEXT NOT NULL DEFAULT '',    -- niche from user prompt (e.g. "footballer big fan")
    username        TEXT NOT NULL,               -- Instagram username
    full_name       TEXT DEFAULT '',
    bio             TEXT DEFAULT '',
    followers_count INTEGER DEFAULT 0,
    following_count INTEGER DEFAULT 0,
    profile_image_url TEXT DEFAULT '',
    detected_language TEXT DEFAULT '',
    total_score     INTEGER DEFAULT 0,
    scores          JSONB DEFAULT '{}',         -- {age, work_lifestyle, occupation, location, side_job_signal}
    confidence      TEXT DEFAULT 'low',
    reasoning       TEXT DEFAULT '',
    discovery_source TEXT DEFAULT '',
    followed        BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- A lead can only appear once per Instagram account + niche combo
CREATE UNIQUE INDEX IF NOT EXISTS uq_qualified_leads_cookie_niche_user
    ON qualified_leads (cookie_id, niche, username);

-- Fast lookups by web-app user
CREATE INDEX IF NOT EXISTS idx_qualified_leads_user_id
    ON qualified_leads (user_id);

-- Fast lookups by niche
CREATE INDEX IF NOT EXISTS idx_qualified_leads_niche
    ON qualified_leads (niche);


-- ═══════════════════════════════════════════════════════════════════
-- RLS policies (anon key access — same pattern as other tables)
-- ═══════════════════════════════════════════════════════════════════

ALTER TABLE qualified_leads ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_insert_qualified_leads"
    ON qualified_leads FOR INSERT
    TO anon
    WITH CHECK (true);

CREATE POLICY "anon_select_qualified_leads"
    ON qualified_leads FOR SELECT
    TO anon
    USING (true);

CREATE POLICY "anon_update_qualified_leads"
    ON qualified_leads FOR UPDATE
    TO anon
    USING (true)
    WITH CHECK (true);

CREATE POLICY "anon_delete_qualified_leads"
    ON qualified_leads FOR DELETE
    TO anon
    USING (true);
