-- P2 docs-assistant — run this in the Supabase SQL editor before first use.

create extension if not exists vector;

-- One row per chunk of an ingested document. Re-ingesting a file deletes its
-- rows first (see the API), so filename is the refresh unit.
create table if not exists chunks (
  id bigint generated always as identity primary key,
  filename text not null,
  chunk_index integer not null,
  page integer,                       -- 1-based PDF page; null for text/markdown
  content text not null,
  embedding vector(1024) not null,    -- dimension must match EMBEDDINGS_DIM
  created_at timestamptz not null default now(),
  unique (filename, chunk_index)
);

create index if not exists chunks_filename_idx on chunks (filename);
create index if not exists chunks_embedding_idx
  on chunks using hnsw (embedding vector_cosine_ops);

-- Cosine-similarity top-k retrieval.
create or replace function match_chunks(
  query_embedding vector(1024),
  match_count int default 5
)
returns table (
  id bigint,
  filename text,
  chunk_index integer,
  page integer,
  content text,
  similarity double precision
)
language sql stable as $$
  select
    id, filename, chunk_index, page, content,
    1 - (embedding <=> query_embedding) as similarity
  from chunks
  order by embedding <=> query_embedding
  limit match_count;
$$;

-- No policies on purpose: only the service-role key (used by the API) can
-- read or write; anon/authenticated clients get nothing.
alter table chunks enable row level security;

-- M2: every /ask is recorded; confident=false rows are the
-- unanswered-questions log shown in the admin view.
create table if not exists questions (
  id bigint generated always as identity primary key,
  question text not null,
  answer text not null,
  confident boolean not null,
  citations jsonb not null default '[]',
  created_at timestamptz not null default now()
);

create index if not exists questions_created_idx on questions (created_at desc);

alter table questions enable row level security;
