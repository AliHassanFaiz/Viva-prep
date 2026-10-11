const KEY = "viva.userId";

function uuid(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
}

export function newId(): string { return uuid(); }

let cached: string | null = null;
export function getUserId(): string {
  if (cached) return cached;
  try {
    let id = localStorage.getItem(KEY);
    if (!id) { id = uuid(); localStorage.setItem(KEY, id); }
    cached = id;
  } catch {
    cached = uuid(); // storage blocked: anonymous for this tab only
  }
  return cached;
}
