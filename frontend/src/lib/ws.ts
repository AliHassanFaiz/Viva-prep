import { settings } from "./settings";

export type WsStatus = "connecting" | "open" | "reconnecting" | "closed";

/** WebSocket with exponential backoff (1s, 2s, 4s, 8s, 16s; 5 tries) and a 20 s keep-alive ping. */
export class CallSocket {
  private ws: WebSocket | null = null;
  private tries = 0;
  private timer: number | undefined;
  private ping: number | undefined;
  private manualClose = false;
  private hasOpened = false;

  constructor(
    private getUrl: () => Promise<string>,
    private h: { onMessage: (m: any) => void; onStatus: (s: WsStatus) => void; onOpen: (reconnect: boolean) => void },
  ) {}

  private retry() {
    if (this.tries >= 5) { this.h.onStatus("closed"); return; }
    const delay = 1000 * 2 ** this.tries++;
    this.h.onStatus("reconnecting");
    this.timer = window.setTimeout(() => this.connect(), delay);
  }

  async connect() {
    this.manualClose = false;
    this.h.onStatus(this.hasOpened ? "reconnecting" : "connecting");
    let url: string;
    try {
      url = await this.getUrl();  // a new short-lived token each time, so reconnects keep working
    } catch (e: any) {
      if (e?.status === 401 || e?.status === 404) { this.h.onStatus("closed"); return; }  // logged out, or not your session
      this.retry();
      return;
    }
    if (this.manualClose) return;
    const ws = new WebSocket(url);
    this.ws = ws;
    ws.onopen = () => {
      const wasReconnect = this.hasOpened;
      this.hasOpened = true;
      this.tries = 0;
      this.h.onStatus("open");
      window.clearInterval(this.ping);
      this.ping = window.setInterval(() => this.send({ type: "ping" }), settings.PING_MS);
      this.h.onOpen(wasReconnect);
    };
    ws.onmessage = (ev) => {
      try { this.h.onMessage(JSON.parse(ev.data)); } catch { /* ignore malformed frames */ }
    };
    ws.onclose = (ev) => {
      window.clearInterval(this.ping);
      if (this.manualClose || ev.code === 4404 || ev.code === 4403 || ev.code === 4401) { this.h.onStatus("closed"); return; }
      this.retry();
    };
    ws.onerror = () => { /* onclose handles retries */ };
  }

  send(msg: object): boolean {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) { this.ws.send(JSON.stringify(msg)); return true; }
    return false;
  }

  close() {
    this.manualClose = true;
    window.clearTimeout(this.timer);
    window.clearInterval(this.ping);
    this.ws?.close();
  }
}
