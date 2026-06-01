import type { PolicyBullet } from './types'

export type BulletSort = 'score' | 'uses' | 'created'

export type ScoreTier = 'high' | 'mid' | 'low' | 'retired'

/** ACE bullet scoring is an integer 1–10 (new=5, retired ≤2). */
export function scoreTier(score: number | undefined, retired?: boolean): ScoreTier {
  const s = typeof score === 'number' ? score : 5
  if (retired || s <= 2) return 'retired'
  if (s >= 8) return 'high'
  if (s >= 5) return 'mid'
  return 'low'
}

export const TIER_META: Record<ScoreTier, { label: string; bar: string; text: string }> = {
  high: { label: 'High (8–10)', bar: 'bg-status-online', text: 'text-status-online' },
  mid: { label: 'Mid (5–7)', bar: 'bg-status-warning', text: 'text-status-warning' },
  low: { label: 'Low (3–4)', bar: 'bg-status-error', text: 'text-status-error' },
  retired: { label: 'Retired (≤2)', bar: 'bg-muted-foreground', text: 'text-muted-foreground' },
}

export interface ScoreDistribution {
  high: number
  mid: number
  low: number
  retired: number
  total: number
}

export function scoreDistribution(bullets: PolicyBullet[]): ScoreDistribution {
  const d: ScoreDistribution = { high: 0, mid: 0, low: 0, retired: 0, total: bullets.length }
  for (const b of bullets) d[scoreTier(b.score, b.retired)] += 1
  return d
}

export function filterBullets(
  bullets: PolicyBullet[],
  { text, hideRetired }: { text: string; hideRetired: boolean },
): PolicyBullet[] {
  const q = text.trim().toLowerCase()
  return bullets.filter((b) => {
    if (hideRetired && b.retired) return false
    if (q && !(b.text || '').toLowerCase().includes(q)) return false
    return true
  })
}

export function sortBullets(bullets: PolicyBullet[], key: BulletSort): PolicyBullet[] {
  const get = (b: PolicyBullet): number => {
    if (key === 'created') return b.created ? Date.parse(b.created) : 0
    const v = b[key]
    return typeof v === 'number' ? v : 0
  }
  return [...bullets].sort((a, b) => get(b) - get(a))
}
