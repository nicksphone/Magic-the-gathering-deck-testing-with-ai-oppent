export function apiBase(configured?: string): string {
  return configured?.trim().replace(/\/+$/, "") || "/api";
}

export function cardMediaUrl(uri: string | undefined, base: string): string | undefined {
  if (!uri) return undefined;
  if (uri.startsWith("http://") || uri.startsWith("https://")) return uri;
  const path = uri.startsWith("/") ? uri : `/${uri}`;
  if (base === "/api" && path.startsWith("/card-images/")) return path;
  return `${base}${path}`;
}
