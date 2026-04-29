export function SkeletonCard() {
  return (
    <div className="rounded-lg overflow-hidden bg-card border border-border animate-pulse">
      <div className="aspect-[2/3] bg-muted" />
      <div className="p-2 space-y-1.5">
        <div className="h-2.5 bg-muted rounded w-4/5" />
        <div className="h-2 bg-muted rounded w-2/5" />
      </div>
    </div>
  )
}
