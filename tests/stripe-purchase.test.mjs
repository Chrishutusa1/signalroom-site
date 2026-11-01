import test from 'node:test';
import assert from 'node:assert/strict';
import { createHmac } from 'node:crypto';
import { createHandler, purchasePayload } from '../netlify/functions/stripe-purchase.mjs';

const now = 1793552400000;
const env = { SITE_ID: '98c71b47-cb1e-4eb2-8255-963349df8ccf', STRIPE_PURCHASE_ENABLED: 'true', STRIPE_PURCHASE_WEBHOOK_SECRET: 'test-local-signing-secret', GA4_SIGNAL_ROOM_API_SECRET: 'local-sr', GA4_TRUE_UP_API_SECRET: 'local-tu' };
const fixture = () => ({ type: 'checkout.session.completed', livemode: true, created: now / 1000 - 10, data: { object: {
  object: 'checkout.session', id: 'cs_live_ExampleSession', livemode: true, mode: 'payment', payment_status: 'paid',
  payment_link: 'plink_1UTZWlLc18Q3MIovf2Xljrio', currency: 'usd', amount_total: 125000,
  customer_details: { email: 'private@example.com', name: 'Private Person' }, metadata: { arbitrary: 'DO NOT FORWARD' },
} } });
function request(event, { secret = env.STRIPE_PURCHASE_WEBHOOK_SECRET, time = now / 1000, mutate = false } = {}) {
  const body = JSON.stringify(event);
  const signature = createHmac('sha256', secret).update(`${time}.${body}`).digest('hex');
  return new Request('https://signalroompodcast.com/.netlify/functions/stripe-purchase', { method: 'POST', body: mutate ? body + ' ' : body,
    headers: { 'stripe-signature': `t=${time},v1=${signature}` } });
}
test('signed paid events route to the correct property and exclude personal data', async () => {
  const calls = [];
  const handler = createHandler({ env, clock: () => now, send: async (url, options) => { calls.push([String(url), JSON.parse(options.body)]); return new Response(null, { status: 204 }); } });
  assert.equal((await handler(request(fixture()))).status, 200);
  assert.match(calls[0][0], /measurement_id=G-RZNHLJSRW3/);
  assert.equal(calls[0][1].events[0].params.value, 1250);
  assert.doesNotMatch(JSON.stringify(calls), /private@example|Private Person|DO NOT FORWARD/);
  const tu = fixture(); tu.data.object.payment_link = 'plink_1UTZWpLc18Q3MIovx6lmyziM';
  tu.type = 'checkout.session.async_payment_succeeded';
  assert.equal((await handler(request(tu))).status, 200);
  assert.match(calls[1][0], /measurement_id=G-50ZJL23B2M/);
});
test('unpaid, test, unrelated and subscription events never transmit', async () => {
  const handler = createHandler({ env, clock: () => now, send: async () => assert.fail('Must not transmit') });
  for (const change of [e => e.livemode = false, e => e.data.object.payment_status = 'unpaid',
    e => e.data.object.mode = 'subscription', e => e.data.object.payment_link = 'unrelated', e => e.type = 'charge.refunded']) {
    const e = fixture(); change(e); assert.equal((await handler(request(e))).status, 200);
  }
});
test('forged, tampered and expired signatures fail closed', async () => {
  const handler = createHandler({ env, clock: () => now, send: async () => assert.fail('Must not transmit') });
  for (const options of [{ secret: 'wrong' }, { mutate: true }, { time: now / 1000 - 301 }]) {
    assert.equal((await handler(request(fixture(), options))).status, 400);
  }
});
test('disabled and preview deployments fail closed; delivery errors are retriable', async () => {
  for (const overrides of [{ STRIPE_PURCHASE_ENABLED: 'false' }, { SITE_ID: 'staging-site' }, { GA4_SIGNAL_ROOM_API_SECRET: '' }]) {
    const handler = createHandler({ env: { ...env, ...overrides }, clock: () => now, send: async () => assert.fail('Must not transmit') });
    assert.equal((await handler(request(fixture()))).status, 503);
  }
  const handler = createHandler({ env, clock: () => now, send: async () => { throw new Error('No network'); } });
  assert.equal((await handler(request(fixture()))).status, 502);
});
test('retries retain transaction and client identifiers; taxes excluded from revenue', () => {
  const a = fixture(), b = fixture(); b.type = 'checkout.session.async_payment_succeeded';
  assert.deepEqual(purchasePayload(a, now), purchasePayload(b, now));
  a.data.object.total_details = { amount_tax: 1000, amount_shipping: 500 };
  assert.equal(purchasePayload(a, now).payload.events[0].params.value, 1235);
  a.data.object.currency = 'jpy'; assert.throws(() => purchasePayload(a, now));
});
