import { useState } from "react";
import { resolveCardMediaUrl } from "../api/client";

/** A failed cached image is not artwork. Never fetch another printing on failure. */
export function CardArt({ uri, name }: { uri?: string; name: string }) {
  const url = resolveCardMediaUrl(uri);
  const [failedUrl, setFailedUrl] = useState<string>();
  return url && failedUrl !== url
    ? <img className="card-art" src={url} alt={name} loading="lazy" onError={() => setFailedUrl(url)} />
    : <span className="card-no-art"><span aria-hidden="true">◇</span><strong>{name}</strong><small>Artwork unavailable</small></span>;
}
