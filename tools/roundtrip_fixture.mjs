// The bookmark round-trip test's fixture, made with the PosterChan extension's OWN code (vaultcore.js seals, the
// vendored nostr bundle signs), so the events are exactly what a paired desktop browser would publish.
//
//   node roundtrip_fixture.mjs make  <posterchan extension dir> <relay ws url> <out dir>
//        -> <out>/code.txt (pairing code), <out>/seed.jsonl (one sealed bookmark, as if from the desktop),
//           <out>/account.json (keys, for `check`)
//   node roundtrip_fixture.mjs check <posterchan extension dir> <out dir> <received.jsonl>
//        -> prints every bookmark the phone published (opened with the vault key), as JSON lines
import fs from 'fs';
import path from 'path';
import vm from 'vm';
import { createRequire } from 'module';
import { webcrypto } from 'crypto';

const [mode, ext, a3, a4, a5] = process.argv.slice(2);
const require = createRequire(import.meta.url);
const V = require(path.join(ext, 'vaultcore.js'));
const ctx = { console, crypto: webcrypto, TextEncoder, TextDecoder, Uint8Array, ArrayBuffer, DataView };
ctx.globalThis = ctx; ctx.self = ctx; ctx.window = ctx;
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(ext, 'vendor/nostr.bundle.js'), 'utf8') + '\n;globalThis.NostrTools = NostrTools;', ctx);
const T = ctx.NostrTools;
const inCtx = vm.runInContext('(s) => JSON.parse(s)', ctx);   // a value of THAT realm (its Array, its Object)
const hex = b => Buffer.from(b).toString('hex');

if (mode === 'make') {
  const [relay, out] = [a3, a4];
  fs.mkdirSync(out, { recursive: true });
  const sk = T.generateSecretKey(), pk = T.getPublicKey(sk);
  const key = V.newVaultKey();
  const code = Buffer.from(JSON.stringify({ t: 'pcvault', pubkey: pk, key: V.toB64(key), relay, mode: 'full', sk: hex(sk) }))
    .toString('base64');
  const item = { title: 'From the desktop', url: 'https://example.com/from-the-desktop', folder: '', root: 'toolbar' };
  // Built INSIDE the bundle's context: its validator checks arrays with that realm's Array.
  const tmpl = inCtx(JSON.stringify({ kind: 30078, created_at: Math.floor(Date.now() / 1000) - 60,
                               content: await V.seal(key, item), tags: [['d', 'pcai:bm:seed-from-desktop'], ['l', 'pcai-bm']] }));
  const ev = T.finalizeEvent(tmpl, sk);
  fs.writeFileSync(path.join(out, 'code.txt'), code);
  fs.writeFileSync(path.join(out, 'seed.jsonl'), JSON.stringify(ev) + '\n');
  fs.writeFileSync(path.join(out, 'account.json'), JSON.stringify({ pk, key: V.toB64(key) }));
  console.log('fixture: account', pk.slice(0, 12), 'seeded', item.url);
} else if (mode === 'check') {
  const [out, received] = [a3, a4];
  const acct = JSON.parse(fs.readFileSync(path.join(out, 'account.json'), 'utf8'));
  const key = V.fromB64(acct.key);
  for (const line of fs.readFileSync(received, 'utf8').split('\n').filter(Boolean)) {
    const ev = JSON.parse(line);
    if (ev.pubkey !== acct.pk || ev.kind !== 30078) continue;
    const d = (ev.tags.find(t => t[0] === 'd') || [])[1] || '';
    if (!d.startsWith('pcai:bm:')) continue;
    let item = null;
    try { item = ev.content ? await V.open(key, ev.content) : null; } catch (_) { item = { unreadable: true }; }
    console.log(JSON.stringify({ d, verified: T.verifyEvent(inCtx(line)), tombstone: !ev.content, item }));
  }
} else {
  console.error('usage: roundtrip_fixture.mjs make|check ...'); process.exit(2);
}
