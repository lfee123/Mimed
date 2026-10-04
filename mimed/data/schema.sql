-- Schema for mimed SQLite Database with CHECK constraints and optimized indexes

CREATE TABLE IF NOT EXISTS campaigns (
    campaign_id TEXT PRIMARY KEY,
    brand TEXT NOT NULL,
    category TEXT NOT NULL,
    platform TEXT NOT NULL,
    total_budget REAL NOT NULL CHECK (total_budget > 0),
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    target_creator_tier TEXT NOT NULL,
    expected_creators INTEGER NOT NULL CHECK (expected_creators > 0)
);

CREATE TABLE IF NOT EXISTS creators (
    creator_id TEXT PRIMARY KEY,
    platform TEXT NOT NULL,
    follower_count INTEGER NOT NULL CHECK (follower_count > 0),
    tier TEXT NOT NULL,
    account_age_months INTEGER NOT NULL CHECK (account_age_months >= 0),
    historical_avg_views_per_post REAL NOT NULL,
    historical_completion_rate REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS posts (
    post_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    creator_id TEXT NOT NULL,
    post_date TEXT NOT NULL,
    platform TEXT NOT NULL,
    category TEXT NOT NULL,
    format TEXT NOT NULL,
    views_at_24h INTEGER NOT NULL CHECK (views_at_24h >= 0),
    views_at_7d INTEGER NOT NULL CHECK (views_at_7d >= views_at_24h),
    views_at_30d INTEGER NOT NULL CHECK (views_at_30d >= views_at_7d),
    views_final INTEGER NOT NULL CHECK (views_final >= views_at_30d),
    total_payout_earned REAL NOT NULL CHECK (total_payout_earned >= 0),
    flagged_suspicious INTEGER NOT NULL DEFAULT 0 CHECK (flagged_suspicious IN (0, 1)),
    FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id),
    FOREIGN KEY (creator_id) REFERENCES creators(creator_id)
);

CREATE TABLE IF NOT EXISTS milestone_ladders (
    campaign_id TEXT NOT NULL,
    milestone_rank INTEGER NOT NULL CHECK (milestone_rank > 0),
    view_threshold INTEGER NOT NULL CHECK (view_threshold > 0),
    payout_amount REAL NOT NULL CHECK (payout_amount >= 0),
    PRIMARY KEY (campaign_id, milestone_rank),
    FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id)
);

-- Optimized Indexes
-- 1. Support temporal filtering of campaign posts by campaign & date
CREATE INDEX IF NOT EXISTS idx_posts_campaign_date ON posts(campaign_id, post_date);

-- 2. Support creator historical performance calculation prior to campaign start date (as-of queries)
CREATE INDEX IF NOT EXISTS idx_posts_creator_date ON posts(creator_id, post_date);

-- 3. Support joining posts by campaign and creator
CREATE INDEX IF NOT EXISTS idx_posts_campaign_creator ON posts(campaign_id, creator_id);

-- 4. Support hierarchical segment retrieval by platform, category, format
CREATE INDEX IF NOT EXISTS idx_posts_segment ON posts(platform, category, format);

-- 5. Support campaign lookup by start date for temporal walk-forward evaluation
CREATE INDEX IF NOT EXISTS idx_campaigns_date ON campaigns(start_date);
