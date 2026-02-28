export const config = { runtime: 'edge' };

export default async function handler(req: Request): Promise<Response> {
  if (req.method !== 'POST') {
    return new Response('Method not allowed', { status: 405 });
  }

  try {
    const body = await req.json() as { errors?: unknown[] };
    const errors = body?.errors;

    if (!Array.isArray(errors) || errors.length === 0) {
      return new Response('No errors', { status: 400 });
    }

    // Log to Vercel's built-in logging (visible in Vercel dashboard)
    for (const err of errors.slice(0, 10)) {
      console.error('[CLIENT_ERROR]', JSON.stringify(err));
    }

    return new Response(JSON.stringify({ received: errors.length }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  } catch {
    return new Response('Invalid payload', { status: 400 });
  }
}
