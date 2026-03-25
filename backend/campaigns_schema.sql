-- ═══════════════════════════════════════════════════════════════════
-- campaigns table — stores campaign settings for lead generation
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS campaigns (
    id                BIGSERIAL PRIMARY KEY,
    user_id           INTEGER NOT NULL,           -- linked to authentication.id
    name              TEXT NOT NULL,
    target_interest   TEXT NOT NULL,
    optional_keywords JSONB DEFAULT '[]'::jsonb,   -- strictly save as json array
    max_profiles      INTEGER DEFAULT 50,
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    updated_at        TIMESTAMPTZ DEFAULT NOW()
);

-- Fast lookups by user
CREATE INDEX IF NOT EXISTS idx_campaigns_user_id ON campaigns (user_id);

-- Apply RLS policies to campaigns
ALTER TABLE campaigns ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_insert_campaigns" ON campaigns FOR INSERT TO anon WITH CHECK (true);
CREATE POLICY "anon_select_campaigns" ON campaigns FOR SELECT TO anon USING (true);
CREATE POLICY "anon_update_campaigns" ON campaigns FOR UPDATE TO anon USING (true) WITH CHECK (true);
CREATE POLICY "anon_delete_campaigns" ON campaigns FOR DELETE TO anon USING (true);


-- ═══════════════════════════════════════════════════════════════════
-- Alter qualified_leads to add campaign_id
-- ═══════════════════════════════════════════════════════════════════
ALTER TABLE qualified_leads 
ADD COLUMN IF NOT EXISTS campaign_id BIGINT REFERENCES campaigns(id) ON DELETE CASCADE;

-- Fast lookups by campaign
CREATE INDEX IF NOT EXISTS idx_qualified_leads_campaign_id ON qualified_leads (campaign_id);
