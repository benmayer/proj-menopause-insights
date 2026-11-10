-- RAG store: reference knowledge + report instructions. NO personal data goes in here.
create extension if not exists vector with schema extensions;

create table if not exists public.documents (
  id bigint primary key generated always as identity,
  section text not null,          -- reference | summary | trend | variability | patterns | flags | caveats | tone
  title text not null,
  content text not null,
  source text,                    -- URL or citation
  embedding extensions.vector(1536) not null,
  unique (section, title)
);

-- RLS on with no policies: the anon/publishable key can read nothing.
-- The server-side secret key bypasses RLS, so only our backend can query.
alter table public.documents enable row level security;

create index if not exists documents_embedding_idx
  on public.documents using hnsw (embedding extensions.vector_cosine_ops);

create or replace function public.match_documents(
  query_embedding extensions.vector(1536),
  match_count int default 3,
  filter_section text default null
)
returns table (id bigint, section text, title text, content text, source text, similarity float)
language sql stable
set search_path = ''
as $$
  select d.id, d.section, d.title, d.content, d.source,
         1 - (d.embedding operator(extensions.<=>) query_embedding) as similarity
  from public.documents d
  where filter_section is null or d.section = filter_section
  order by d.embedding operator(extensions.<=>) query_embedding
  limit match_count;
$$;
