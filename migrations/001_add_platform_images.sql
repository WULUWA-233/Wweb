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

CREATE INDEX IF NOT EXISTS idx_platform_images_order
    ON platform_images(platform_id, is_primary DESC, sort_order, id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_platform_images_one_primary
    ON platform_images(platform_id) WHERE is_primary = 1;
