export function formatTomans(value?: number | null) {
  if (!value) return "-";
  
  if (value >= 1_000_000_000) {
    const billions = value / 1_000_000_000;
    return `${billions.toLocaleString("en-US", { maximumFractionDigits: 1 })} میلیارد`;
  }
  
  if (value >= 1_000_000) {
    const millions = value / 1_000_000;
    return `${millions.toLocaleString("en-US", { maximumFractionDigits: 1 })} میلیون`;
  }
  
  return value.toLocaleString("en-US");
}

export function formatDate(dateString?: string | null) {
  if (!dateString) return "-";
  try {
    const d = new Date(dateString);
    return new Intl.DateTimeFormat("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(d);
  } catch (e) {
    return dateString;
  }
}
