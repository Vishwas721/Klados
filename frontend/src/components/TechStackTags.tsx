export function TechStackTags({ tech }: { tech: string[] }) {
  if (!tech || tech.length === 0) {
    return <span className="text-xs text-gray-400">—</span>;
  }

  return (
    <div className="flex flex-wrap gap-1">
      {tech.map((t) => (
        <span
          key={t}
          className="rounded bg-indigo-50 px-1.5 py-0.5 text-xs font-medium text-indigo-700"
        >
          {t}
        </span>
      ))}
    </div>
  );
}
