export function httpErrorMessage(text: string, status: number): string {
  let body: unknown;
  try { body = JSON.parse(text); } catch { return text || `HTTP ${status}`; }
  if (!body || typeof body !== "object" || !("detail" in body)) return text || `HTTP ${status}`;
  const detail = body.detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && "message" in detail && typeof detail.message === "string") return detail.message;
  if (Array.isArray(detail)) {
    const messages = detail.flatMap((item: unknown) => {
      if (!item || typeof item !== "object" || !("msg" in item) || typeof item.msg !== "string") return [];
      const location = "loc" in item && Array.isArray(item.loc) ? item.loc.join(".") : "request";
      return [`${location}: ${item.msg}`];
    });
    if (messages.length) return messages.join("; ");
  }
  return text || `HTTP ${status}`;
}
