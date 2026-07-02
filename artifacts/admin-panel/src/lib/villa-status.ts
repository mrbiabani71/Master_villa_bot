export type VillaStatus = "draft" | "published" | "sold" | "archived";

export const STATUS_LABELS: Record<VillaStatus, string> = {
  draft: "Draft",
  published: "Published",
  sold: "Sold",
  archived: "Archived",
};

export const STATUS_BADGE_CLASSES: Record<VillaStatus, string> = {
  draft:
    "bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-600",
  published:
    "bg-emerald-100 text-emerald-700 border-emerald-200 dark:bg-emerald-900 dark:text-emerald-300 dark:border-emerald-700",
  sold: "bg-blue-100 text-blue-700 border-blue-200 dark:bg-blue-900 dark:text-blue-300 dark:border-blue-700",
  archived:
    "bg-amber-100 text-amber-700 border-amber-200 dark:bg-amber-900 dark:text-amber-300 dark:border-amber-700",
};

export const ALL_STATUSES: VillaStatus[] = [
  "draft",
  "published",
  "sold",
  "archived",
];
