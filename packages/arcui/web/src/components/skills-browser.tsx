import { useMemo, useState } from 'react'
import { LayoutGrid, List, Sparkles } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import { relativeTime } from '@/lib/format'
import { SkillDrawer, type SkillRef } from '@/components/skill-drawer'

function matches(s: SkillRef, q: string): boolean {
  if (!q) return true
  const hay = `${s.name ?? ''} ${s.description ?? ''} ${s.agent_id ?? ''} ${s.triggers ?? ''}`.toLowerCase()
  return hay.includes(q.toLowerCase())
}

/** Shared skill explorer: filter + list/cards toggle + click-to-open formatted
 *  detail. `agentId` scopes the detail fetch when skills lack an inline body. */
export function SkillsBrowser({ skills, agentId }: { skills: SkillRef[]; agentId?: string }) {
  const [view, setView] = useState<'list' | 'cards'>('list')
  const [filter, setFilter] = useState('')
  const [active, setActive] = useState<SkillRef | null>(null)

  const filtered = useMemo(() => skills.filter((s) => matches(s, filter)), [skills, filter])

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <Input
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter skills…"
          className="h-8 max-w-xs"
        />
        <span className="text-xs text-muted-foreground">{filtered.length} of {skills.length}</span>
        <div className="ml-auto inline-flex overflow-hidden rounded-lg border border-border">
          <button
            type="button"
            onClick={() => setView('list')}
            className={cn(
              'flex cursor-pointer items-center gap-1 px-2.5 py-1 text-xs',
              view === 'list' ? 'bg-muted text-foreground' : 'text-muted-foreground hover:bg-muted/50',
            )}
          >
            <List className="size-3.5" /> List
          </button>
          <button
            type="button"
            onClick={() => setView('cards')}
            className={cn(
              'flex cursor-pointer items-center gap-1 border-l border-border px-2.5 py-1 text-xs',
              view === 'cards' ? 'bg-muted text-foreground' : 'text-muted-foreground hover:bg-muted/50',
            )}
          >
            <LayoutGrid className="size-3.5" /> Cards
          </button>
        </div>
      </div>

      {filtered.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted-foreground">No matching skills</p>
      ) : view === 'list' ? (
        <div className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-card">
          {filtered.map((s, i) => (
            <button
              key={`${s.name}-${i}`}
              type="button"
              onClick={() => setActive(s)}
              className="flex w-full cursor-pointer items-center gap-3 px-4 py-2.5 text-left hover:bg-muted/40"
            >
              <Sparkles className="size-4 shrink-0 text-primary" />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="truncate font-medium text-foreground">{s.name || 'unnamed'}</span>
                  {s.version && (
                    <span className="shrink-0 rounded border border-border bg-muted/40 px-1 py-0.5 font-mono text-[10px] text-muted-foreground">v{s.version}</span>
                  )}
                </div>
                {s.description && <p className="truncate text-xs text-muted-foreground">{s.description}</p>}
              </div>
              {s.agent_id && <span className="shrink-0 font-mono text-[11px] text-muted-foreground">{s.agent_id}</span>}
              {s.mtime != null && <span className="shrink-0 text-[11px] text-muted-foreground">{relativeTime(s.mtime as number)}</span>}
            </button>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((s, i) => (
            <button
              key={`${s.name}-${i}`}
              type="button"
              onClick={() => setActive(s)}
              className="cursor-pointer rounded-xl border border-border bg-card p-4 text-left shadow-xs transition-colors hover:border-primary/40 hover:bg-muted/30"
            >
              <div className="flex items-center gap-2">
                <Sparkles className="size-4 shrink-0 text-primary" />
                <span className="truncate font-medium text-foreground">{s.name || 'unnamed'}</span>
                {s.version && (
                  <span className="shrink-0 rounded border border-border bg-muted/40 px-1 py-0.5 font-mono text-[10px] text-muted-foreground">v{s.version}</span>
                )}
              </div>
              {s.agent_id && <div className="mt-1 font-mono text-[11px] text-muted-foreground">{s.agent_id}</div>}
              {s.description && <p className="mt-2 line-clamp-3 text-xs text-muted-foreground">{s.description}</p>}
            </button>
          ))}
        </div>
      )}

      <SkillDrawer
        skill={active}
        agentId={agentId ?? active?.agent_id}
        open={!!active}
        onOpenChange={(o) => !o && setActive(null)}
      />
    </div>
  )
}
