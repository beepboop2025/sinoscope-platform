export const config = { runtime: 'edge' };

export default async function handler(req: Request): Promise<Response> {
  const url = new URL(req.url);
  const upstream = `https://query1.finance.yahoo.com${url.pathname.replace(/^\/api\/yahoo/, '')}${url.search}`;

  const res = await fetch(upstream, {
    headers: { 'User-Agent': 'DragonScope/1.0' },
  });

  return new Response(res.body, {
    status: res.status,
    headers: {
      'Content-Type': res.headers.get('Content-Type') || 'application/json',
      'Cache-Control': 'public, s-maxage=60, stale-while-revalidate=120',
    },
  });
}
