PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS platforms (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    country TEXT NOT NULL,
    batch INTEGER NOT NULL CHECK (batch IN (1, 2)),
    label TEXT NOT NULL CHECK (label IN ('L', 'L/W', 'W')),
    platform_type TEXT,
    payload_description TEXT,
    length_text TEXT,
    beam_draft_text TEXT,
    weight_displacement_text TEXT,
    payload_text TEXT,
    speed_text TEXT,
    range_text TEXT,
    endurance_text TEXT,
    propulsion_sea_text TEXT,
    control_people TEXT,
    evidence_code TEXT CHECK (evidence_code IN ('E2', 'E3', 'E4', 'E5') OR evidence_code IS NULL),
    evidence_raw TEXT,
    verification_note TEXT,
    source_sheet TEXT NOT NULL,
    source_row INTEGER NOT NULL,
    UNIQUE (source_sheet, source_row)
);

CREATE TABLE IF NOT EXISTS activities (
    id INTEGER PRIMARY KEY,
    platform_id INTEGER NOT NULL REFERENCES platforms(id) ON DELETE CASCADE,
    sequence_no INTEGER NOT NULL,
    description TEXT NOT NULL,
    UNIQUE (platform_id, sequence_no)
);

CREATE TABLE IF NOT EXISTS source_links (
    id INTEGER PRIMARY KEY,
    platform_id INTEGER NOT NULL REFERENCES platforms(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('performance', 'activity', 'control')),
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    UNIQUE (platform_id, role, url)
);

CREATE TABLE IF NOT EXISTS platform_images (
    id INTEGER PRIMARY KEY,
    platform_id INTEGER NOT NULL REFERENCES platforms(id) ON DELETE CASCADE,
    image_url TEXT,
    local_path TEXT,
    caption TEXT,
    source_url TEXT,
    source_name TEXT,
    image_type TEXT NOT NULL DEFAULT 'other'
        CHECK (image_type IN ('official', 'exercise', 'combat', 'manufacturer', 'control', 'loading', 'other')),
    is_primary INTEGER NOT NULL DEFAULT 0 CHECK (is_primary IN (0, 1)),
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (image_url IS NOT NULL OR local_path IS NOT NULL),
    CHECK (image_url IS NULL OR image_url LIKE 'http://%' OR image_url LIKE 'https://%'),
    CHECK (source_url IS NULL OR source_url LIKE 'http://%' OR source_url LIKE 'https://%')
);

CREATE INDEX IF NOT EXISTS idx_platforms_filters ON platforms(batch, label, evidence_code, country);
CREATE INDEX IF NOT EXISTS idx_activities_platform ON activities(platform_id);
CREATE INDEX IF NOT EXISTS idx_sources_platform ON source_links(platform_id, role);
CREATE INDEX IF NOT EXISTS idx_platform_images_order ON platform_images(platform_id, is_primary DESC, sort_order, id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_platform_images_one_primary
    ON platform_images(platform_id) WHERE is_primary = 1;
