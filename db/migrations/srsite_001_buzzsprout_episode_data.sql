-- srsite_001_buzzsprout_episode_data
-- Live Neon home for the raw per-episode Buzzsprout enrichment that used to land
-- in the Airtable "Buzzsprout Episode Data" table (app3hF8k8ZGXvf9XF / tblrji2ivwJQYE6Rg),
-- retired in the 2026-11 Airtable->Neon sunset. signalroom-airtable-bridge.py now
-- upserts here; podcast_episode remains the curated hub and links in by
-- podcast_episode_id (declared FK). Seeded once from the 2026-11-03 Airtable backup.
--
-- Standard: identity PK, airtable_id provenance (unique), declared FK to
-- podcast_episode, shared set_updated_at() BEFORE UPDATE trigger, indexes for the
-- query paths (guid match key, buzzsprout id, episode number).

-- migrate:up
create table if not exists buzzsprout_episode_data (
  id                    bigint generated always as identity primary key,
  airtable_id           text unique,
  guid                  text not null unique,
  buzzsprout_episode_id text,
  podcast_episode_id    bigint references podcast_episode(id) on delete set null,
  episode_number        integer,
  title                 text,
  show_name             text,
  podcast_id            text,
  publish_date          date,
  episode_url           text,
  audio_url             text,
  download_url          text,
  duration_seconds      integer,
  description           text,
  show_notes_html       text,
  tags                  text,
  artwork_url           text,
  transcript_raw        text,
  transcript_source     text,
  transcript_url        text,
  chapters              text,
  total_plays           integer,
  unique_listeners      integer,
  explicit              text,
  season                integer,
  language              text,
  buzzsprout_status     text,
  stats_url             text,
  notes                 text,
  hq                    boolean,
  magic_mastering       boolean,
  private               boolean,
  created_at_buzzsprout date,
  updated_at_buzzsprout date,
  inactive_at           timestamptz,
  last_api_sync         date,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now()
);

create index if not exists buzzsprout_episode_data_bz_id_idx
  on buzzsprout_episode_data (buzzsprout_episode_id);
create index if not exists buzzsprout_episode_data_episode_number_idx
  on buzzsprout_episode_data (episode_number);
create index if not exists buzzsprout_episode_data_podcast_episode_id_idx
  on buzzsprout_episode_data (podcast_episode_id);

drop trigger if exists buzzsprout_episode_data_set_updated_at on buzzsprout_episode_data;
create trigger buzzsprout_episode_data_set_updated_at
  before update on buzzsprout_episode_data
  for each row execute function set_updated_at();

-- migrate:down
drop table if exists buzzsprout_episode_data;
