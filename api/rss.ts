export const config = { runtime: 'edge' };

export default async function handler(req: Request): Promise<Response> {
  const url = new URL(req.url);
  const upstream = `https://api.rss2json.com${url.pathname.replace(/^\/api\/rss/, '')}${url.search}`;

  const res = await fetch(upstream, {
    headers: { 'User-Agent': 'DragonScope/1.0' },
  });

  return new Response(res.body, {
    status: res.status,
    headers: {
      'Content-Type': res.headers.get('Content-Type') || 'application/json',
      'Cache-Control': 'public, s-maxage=300, stale-while-revalidate=600',
    },
  });
}
