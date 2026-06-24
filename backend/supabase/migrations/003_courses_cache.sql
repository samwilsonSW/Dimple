-- Courses cache table for GolfCourseAPI.com data
-- Fetched on-demand, stored to reduce API calls

create table if not exists courses (
    id uuid default gen_random_uuid() primary key,
    external_id text not null unique,           -- GolfCourseAPI.com course ID
    name text not null,
    club_name text,
    city text,
    state text,
    country text,
    holes_count int default 18,
    tee_data jsonb default '[]',                -- Array of tee box objects
    hole_data jsonb default '[]',               -- Array of hole objects (par, yardage, handicap)
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

-- Index for fast lookups by external ID
create index if not exists idx_courses_external_id on courses(external_id);

-- Enable RLS
alter table courses enable row level security;

-- Allow all reads (course data is public)
create policy "Allow public read access on courses"
    on courses for select
    using (true);

-- Allow inserts (for caching)
create policy "Allow insert on courses"
    on courses for insert
    with check (true);
