export interface Env {
  // Documented in .dev.vars.example. Secrets are only ever read from the environment.
  OCR_API_KEY?: string;
  VAPID_PUBLIC_KEY?: string;
  VAPID_PRIVATE_KEY?: string;
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });

export default {
  async fetch(request: Request, _env: Env): Promise<Response> {
    const { pathname } = new URL(request.url);

    if (pathname === '/receipt') {
      if (request.method !== 'POST') return json({ error: 'method not allowed' }, 405);
      // TODO: receive the receipt photo (multipart/form-data), run OCR, and return the
      // recognised ingredients mapped to canonical ids. Not implemented yet.
      return json({ error: 'not implemented' }, 501);
    }

    return json({ error: 'not found' }, 404);
  },

  async scheduled(_controller: ScheduledController, _env: Env): Promise<void> {
    // TODO: check pantry item expiry dates (shelf_life_days) and send notifications.
    // Not implemented yet.
  },
} satisfies ExportedHandler<Env>;
