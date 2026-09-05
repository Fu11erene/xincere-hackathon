-- 概念/論理モデル: .claude/rules/data-model.md 参照
-- 認証・データ分離方針: .claude/rules/auth-and-data-isolation.md 参照
--   バックエンドはservice_roleキーで接続し、全クエリでuser_idフィルタを明示することを
--   データ分離の主たる担保とする。ここでのRLSはあくまで保険。

create table projects (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users (id) on delete cascade,
    goal_text text not null,
    deadline date,
    created_at timestamptz not null default now()
);

create index projects_user_id_idx on projects (user_id);

create table tasks (
    id uuid primary key default gen_random_uuid(),
    project_id uuid not null references projects (id) on delete cascade,
    name text not null,
    category text not null,
    original_estimated_duration_hours numeric not null,
    current_estimated_duration_hours numeric not null,
    status text not null default 'todo'
        check (status in ('todo', 'in_progress', 'done', 'skipped')),
    actual_start_at timestamptz,
    actual_end_at timestamptz,
    skip_count integer not null default 0,
    created_at timestamptz not null default now()
);

create index tasks_project_id_idx on tasks (project_id);

create table task_dependencies (
    id uuid primary key default gen_random_uuid(),
    task_id uuid not null references tasks (id) on delete cascade,
    depends_on_task_id uuid not null references tasks (id) on delete cascade,
    unique (task_id, depends_on_task_id)
);

create index task_dependencies_task_id_idx on task_dependencies (task_id);
create index task_dependencies_depends_on_task_id_idx on task_dependencies (depends_on_task_id);

create table progress_events (
    id uuid primary key default gen_random_uuid(),
    task_id uuid not null references tasks (id) on delete cascade,
    event_type text not null check (event_type in ('complete', 'skip')),
    occurred_at timestamptz not null default now(),
    actual_duration_hours numeric
);

create index progress_events_task_id_idx on progress_events (task_id);

create table user_pace_profile (
    user_id uuid primary key references auth.users (id) on delete cascade,
    pace_coefficient numeric not null default 1.0,
    skip_rate_by_category jsonb not null default '{}'::jsonb,
    updated_at timestamptz not null default now()
);

-- RLS: バックエンドはservice_roleで接続するため実質バイパスされるが、保険として有効化する。

alter table projects enable row level security;
alter table tasks enable row level security;
alter table task_dependencies enable row level security;
alter table progress_events enable row level security;
alter table user_pace_profile enable row level security;

create policy "projects_owner" on projects
    for all
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

create policy "tasks_owner" on tasks
    for all
    using (exists (
        select 1 from projects
        where projects.id = tasks.project_id
        and projects.user_id = auth.uid()
    ))
    with check (exists (
        select 1 from projects
        where projects.id = tasks.project_id
        and projects.user_id = auth.uid()
    ));

create policy "task_dependencies_owner" on task_dependencies
    for all
    using (exists (
        select 1 from tasks
        join projects on projects.id = tasks.project_id
        where tasks.id = task_dependencies.task_id
        and projects.user_id = auth.uid()
    ))
    with check (exists (
        select 1 from tasks
        join projects on projects.id = tasks.project_id
        where tasks.id = task_dependencies.task_id
        and projects.user_id = auth.uid()
    ));

create policy "progress_events_owner" on progress_events
    for all
    using (exists (
        select 1 from tasks
        join projects on projects.id = tasks.project_id
        where tasks.id = progress_events.task_id
        and projects.user_id = auth.uid()
    ))
    with check (exists (
        select 1 from tasks
        join projects on projects.id = tasks.project_id
        where tasks.id = progress_events.task_id
        and projects.user_id = auth.uid()
    ));

create policy "user_pace_profile_owner" on user_pace_profile
    for all
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);
