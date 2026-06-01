import { useQuery } from '@tanstack/react-query'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { Markdown } from '@/components/markdown'
import { LoadingRows, ErrorState } from '@/components/states'
import { apiGet } from '@/lib/api'
import type { Dict, SkillsResponse } from '@/lib/types'

export interface SkillRef extends Dict {
  name?: string
  description?: string
  version?: string
  path?: string
  agent_id?: string
  source?: string
  triggers?: string
  body?: string
}

/** Drop leading `---` frontmatter so the prose renders cleanly. */
function stripFrontmatter(text: string): string {
  return text.replace(/^---\s*\n[\s\S]*?\n---\s*\n/, '')
}

/** Slide-over that renders a skill's formatted SKILL.md.
 *  Uses the inlined `body` when present (agent-detail), otherwise fetches the
 *  owning agent's skills and matches by path/name (fleet view). */
export function SkillDrawer({
  skill,
  agentId,
  open,
  onOpenChange,
}: {
  skill: SkillRef | null
  agentId?: string | null
  open: boolean
  onOpenChange: (o: boolean) => void
}) {
  const aid = agentId ?? skill?.agent_id ?? null
  const needFetch = open && !!skill && skill.body == null && !!aid
  const q = useQuery<SkillsResponse>({
    queryKey: ['agent', aid, 'skills'],
    queryFn: ({ signal }) => apiGet(`/api/agents/${aid}/skills`, signal),
    enabled: needFetch,
  })

  let body = skill?.body
  if (body == null && q.data) {
    const match = (q.data.skills as SkillRef[]).find(
      (s) => (skill?.path && s.path === skill.path) || s.name === skill?.name,
    )
    body = match?.body
  }

  const meta = [
    skill?.agent_id ?? agentId,
    skill?.version ? `v${skill.version}` : null,
    skill?.source,
  ]
    .filter(Boolean)
    .join(' · ')

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="flex w-full flex-col gap-0 overflow-hidden p-0 sm:max-w-2xl">
        <SheetHeader className="border-b border-border px-5 py-4">
          <SheetTitle className="text-sm">{skill?.name ?? 'Skill'}</SheetTitle>
          <SheetDescription>{meta || '—'}</SheetDescription>
        </SheetHeader>
        <div className="flex-1 overflow-auto p-5">
          {needFetch && q.isLoading && <LoadingRows rows={6} />}
          {needFetch && q.isError && <ErrorState error={q.error} />}
          {body != null ? (
            <Markdown>{stripFrontmatter(body)}</Markdown>
          ) : (
            !q.isLoading && <p className="text-sm text-muted-foreground">No skill content available.</p>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}
