import { createHmac, createHash, timingSafeEqual } from 'node:crypto';

// Explicit offer allowlist. Unrelated brands, invoices, subscriptions and test
// events never become purchases here. Keep secrets in Netlify Functions only.
export const offers = Object.freeze({
  plink_1UTZWxLc18Q3MIov2JdKj2XH: ['signal_room', 'partner_brief'],
  plink_1UTZWwLc18Q3MIovGU2jDVog: ['signal_room', 'deep_dive_panel'],
  plink_1UTZWvLc18Q3MIovrXIwcb3Q: ['signal_room', 'alumni_refresh'],
  plink_1UTZWuLc18Q3MIovCOpmTwlI: ['signal_room', 'article'],
  plink_1UTZWuLc18Q3MIovZSmXc5wt: ['signal_room', 'promo_upgrade'],
  plink_1UTZWtLc18Q3MIov19nHi1Cf: ['signal_room', 'special_edition_live'],
  plink_1UTZWsLc18Q3MIovNOi4BneQ: ['signal_room', 'special_edition_true_up_launch'],
  plink_1UTZWrLc18Q3MIovRHH4cNQK: ['signal_room', 'special_edition'],
  plink_1UTZWnLc18Q3MIovabZLcu4w: ['signal_room', 'sponsor_quarter'],
  plink_1UTZWmLc18Q3MIovg1NHr0Fj: ['signal_room', 'sponsor_four_episodes'],
  plink_1UTZWlLc18Q3MIovf2Xljrio: ['signal_room', 'sponsor_single_episode'],
  plink_1UTZUaLc18Q3MIovz0BVXFUy: ['signal_room', 'podcast_starter'],
  plink_1UTZWqLc18Q3MIov1DhfaKCk: ['true_up', 'founding_presenting_sponsor'],
  plink_1UTZWqLc18Q3MIovheDpco5P: ['true_up', 'sponsor_four_episodes'],
  plink_1UTZWpLc18Q3MIovx6lmyziM: ['true_up', 'sponsor_single_episode'],
  plink_1UPTqJLc18Q3MIovD6fDkjjL: ['true_up', 'newsletter_placement'],
});
const destinations = {
  signal_room: ['G-RZNHLJSRW3', 'GA4_SIGNAL_ROOM_API_SECRET'],
  true_up: ['G-50ZJL23B2M', 'GA4_TRUE_UP_API_SECRET'],
};
const types = new Set(['checkout.session.completed', 'checkout.session.async_payment_succeeded']);
const reply = (status, text) => new Response(text, { status, headers: { 'Cache-Control': 'no-store' } });

export function validSignature(body, header, secret, now) {
  if (!header || !secret) return false;
  const parts = header.split(',').map(p => p.trim().split('='));
  const timestamp = parts.find(([k]) => k === 't')?.[1];
  if (!/^\d+$/.test(timestamp || '') || Math.abs(now / 1000 - Number(timestamp)) > 300) return false;
  const expected = createHmac('sha256', secret).update(`${timestamp}.${body}`).digest();
  return parts.some(([k, v]) => k === 'v1' && /^[a-f0-9]{64}$/i.test(v || '') && timingSafeEqual(expected, Buffer.from(v, 'hex')));
}

export function purchasePayload(event, now) {
  const s = event.data?.object;
  if (!types.has(event.type) || event.livemode !== true || s?.livemode !== true ||
      s.object !== 'checkout.session' || s.mode !== 'payment' || s.payment_status !== 'paid') return null;
  const offer = offers[s.payment_link];
  if (!offer) return null;
  if (!/^cs_live_[A-Za-z0-9]+$/.test(s.id || '') || s.currency !== 'usd' ||
      !Number.isSafeInteger(s.amount_total) || s.amount_total <= 0) throw new Error('Invalid supported payment');
  const tax = s.total_details?.amount_tax ?? 0;
  const shipping = s.total_details?.amount_shipping ?? 0;
  if (![tax, shipping].every(n => Number.isSafeInteger(n) && n >= 0) || tax + shipping > s.amount_total) throw new Error('Invalid totals');
  const [brand, item] = offer;
  const value = (s.amount_total - tax - shipping) / 100;
  // Stable opaque identifiers let GA4 deduplicate repeated delivery of a session.
  // This is a transaction-only client, not a fabricated website visitor/session.
  const hash = createHash('sha256').update(s.id).digest('hex');
  const payload = {
    client_id: `stripe.${hash.slice(0, 32)}`,
    consent: { ad_user_data: 'DENIED', ad_personalization: 'DENIED' },
    events: [{ name: 'purchase', params: {
      transaction_id: `stripe_${hash.slice(0, 32)}`, currency: 'USD', value,
      tax: tax / 100, shipping: shipping / 100, property_brand: brand,
      measurement_source: 'stripe_verified',
      items: [{ item_id: item, item_name: item.replaceAll('_', ' '), price: value, quantity: 1 }],
    } }],
  };
  if (Number.isSafeInteger(event.created) && event.created <= now / 1000 && now / 1000 - event.created < 72 * 3600) {
    payload.timestamp_micros = event.created * 1000000;
  }
  return { brand, payload };
}

export function createHandler({ env = process.env, send = fetch, clock = Date.now } = {}) {
  return async request => {
    if (request.method !== 'POST') return reply(405, 'POST required');
    if (env.SITE_ID !== '98c71b47-cb1e-4eb2-8255-963349df8ccf' || new URL(request.url).hostname !== 'signalroompodcast.com' || env.STRIPE_PURCHASE_ENABLED !== 'true' || !env.STRIPE_PURCHASE_WEBHOOK_SECRET) return reply(503, 'Not enabled');
    if (Number(request.headers.get('content-length')) > 262144) return reply(413, 'Too large');
    const body = await request.text();
    if (Buffer.byteLength(body) > 262144) return reply(413, 'Too large');
    const now = clock();
    if (!validSignature(body, request.headers.get('stripe-signature'), env.STRIPE_PURCHASE_WEBHOOK_SECRET, now)) return reply(400, 'Invalid signature');
    let purchase;
    try { purchase = purchasePayload(JSON.parse(body), now); }
    catch { return reply(400, 'Invalid event'); }
    if (!purchase) return reply(200, 'Ignored');
    const [measurementId, secretName] = destinations[purchase.brand];
    const secret = env[secretName];
    if (!secret) return reply(503, 'Destination not configured');
    const url = new URL('https://www.google-analytics.com/mp/collect');
    url.searchParams.set('measurement_id', measurementId);
    url.searchParams.set('api_secret', secret);
    try {
      const response = await send(url, { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(purchase.payload), signal: AbortSignal.timeout(8000) });
      if (!response.ok) return reply(502, 'Analytics delivery failed');
    } catch { return reply(502, 'Analytics delivery failed'); }
    return reply(200, 'Accepted');
  };
}
export default createHandler();
