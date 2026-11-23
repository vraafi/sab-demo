#!/usr/bin/env node
/**
 * CRM API — server rujukan untuk poin 4 (sinkron dua arah).
 *
 * Ini bukan tiruan di dalam satu proses. Ini server HTTP sungguhan yang bisa
 * dipanggil dengan curl, Postman, atau workflow n8n. Tujuannya satu: supaya
 * "belum tersambung ke API CRM" berubah menjadi "tersambung ke API CRM yang
 * berjalan; tinggal tukar base URL dan kredensial ke CRM SAB".
 *
 * Tanpa dependensi. Node 22 punya http, crypto, dan fs yang cukup. Alasannya
 * bukan kesukaan: setiap dependensi adalah hal yang harus diperbarui, dan
 * server 600 baris yang bisa dibaca seluruhnya lebih mudah dipercaya daripada
 * framework yang perilakunya harus dicari di dokumentasi.
 *
 * Empat keputusan yang diambil dari praktik yang berlaku November 2026:
 *
 * 1. ETag + If-Match untuk konkurensi optimistis (Azure Architecture Center,
 *    "RESTful Web API Implementation Best Practices"). Server menolak tulisan
 *    kalau versi yang dipegang klien sudah basi. Tanpa ini, dua penulis
 *    terakhir saling menimpa tanpa ada yang tahu.
 *
 * 2. Idempotency-Key untuk POST dan PATCH. Pengiriman ulang adalah hal normal,
 *    bukan kesalahan: webhook bersifat at-least-once, dan klien yang timeout
 *    akan mencoba lagi. Tanpa kunci idempoten, satu percobaan ulang menjadi
 *    dua kontak.
 *
 * 3. Kursor delta berupa bilangan urut naik (`seq`), BUKAN `updated_at`.
 *    Jam dua sistem tidak pernah sama, dan `updated_at` bisa mundur karena
 *    NTP. `seq` hanya bisa maju. Ini alasan yang sama dengan alasan poin 4
 *    menolak last-write-wins: jam tidak boleh jadi wasit.
 *
 * 4. Webhook ditandatangani HMAC-SHA256 atas `timestamp.body`, dengan
 *    timestamp ditolak kalau lebih tua dari 5 menit. Tanda tangan saja tidak
 *    cukup: tanpa batas waktu, satu permintaan sah bisa diputar ulang
 *    selamanya.
 *
 * Jalankan:
 *   node server.js                       # port 8787
 *   PORT=9000 API_KEY=rahasia node server.js
 */
'use strict';

const http = require('node:http');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');

// ---------------------------------------------------------------------------
// Konfigurasi
// ---------------------------------------------------------------------------

const PORT = Number(process.env.PORT || 8787);
const API_KEY = process.env.API_KEY || 'kunci-demo-sab';
const WEBHOOK_SECRET = process.env.WEBHOOK_SECRET || 'rahasia-webhook-sab';
const DB = process.env.DB_PATH || path.join(__dirname, 'data_crm.json');
const BATAS_BODY = 1024 * 1024;        // 1 MB, cukup untuk kontak
const TOLERANSI_WAKTU = 5 * 60 * 1000; // 5 menit untuk tanda tangan webhook

// ---------------------------------------------------------------------------
// Keadaan
// ---------------------------------------------------------------------------

const db = {
  seq: 0,
  kontak: {},      // id -> {id, versi, seq, dihapus, field: {...}}
  audit: [],       // riwayat perubahan, dipakai untuk menjawab "siapa mengubah apa"
  konflik: {},     // "id|field" -> {id, field, dasar, sekarang, diusulkan, pada}
  idempoten: {},   // Idempotency-Key -> {status, body, pada}
  langganan: [],   // webhook subscriber
  pengiriman: [],  // log pengiriman webhook
  masuk: [],       // id event yang sudah diterima, untuk menolak putar ulang
};

function muat() {
  try {
    Object.assign(db, JSON.parse(fs.readFileSync(DB, 'utf8')));
  } catch {
    /* berkas belum ada: mulai kosong */
  }
}

let tulisTertunda = null;
function simpan() {
  // Ditunda 50 ms supaya satu permintaan dengan 20 field tidak menulis 20 kali.
  if (tulisTertunda) return;
  tulisTertunda = setTimeout(() => {
    tulisTertunda = null;
    const tmp = DB + '.tmp';
    fs.writeFileSync(tmp, JSON.stringify(db));
    fs.renameSync(tmp, DB);          // rename bersifat atomik di sistem berkas yang sama
  }, 50);
}

function catat(aksi, id, field, dari, ke, aktor) {
  db.seq += 1;
  db.audit.push({
    seq: db.seq, pada: new Date().toISOString(), aktor,
    aksi, id, field, dari, ke,
  });
  return db.seq;
}

// ---------------------------------------------------------------------------
// Utilitas HTTP
// ---------------------------------------------------------------------------

function kirim(res, kode, isi, kepala = {}) {
  const badan = isi === undefined ? '' : JSON.stringify(isi);
  res.writeHead(kode, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': Buffer.byteLength(badan),
    ...kepala,
  });
  res.end(badan);
}

function salah(res, kode, kode_error, pesan, tambahan = {}) {
  kirim(res, kode, { error: kode_error, pesan, ...tambahan });
}

function samaAman(a, b) {
  const x = Buffer.from(String(a));
  const y = Buffer.from(String(b));
  if (x.length !== y.length) return false;
  return crypto.timingSafeEqual(x, y);
}

function etag(k) {
  return `"${k.id}.${k.versi}"`;
}

function publik(k) {
  if (!k) return null;
  return {
    id: k.id,
    versi: k.versi,
    seq: k.seq,
    dihapus: !!k.dihapus,
    ...k.field,
    updated_at: k.updated_at || null,
  };
}

// ---------------------------------------------------------------------------
// Webhook: tanda tangan, batas waktu, percobaan ulang
// ---------------------------------------------------------------------------

function tandaTangan(waktu, badan) {
  return crypto
    .createHmac('sha256', WEBHOOK_SECRET)
    .update(`${waktu}.${badan}`)
    .digest('hex');
}

async function kirimWebhook(kejadian) {
  if (!db.langganan.length) return;
  const badan = JSON.stringify(kejadian);

  for (const l of db.langganan) {
    const waktu = Date.now();
    const sig = tandaTangan(waktu, badan);
    let hasil = { url: l.url, kejadian: kejadian.id, percobaan: 0, status: 0 };

    // at-least-once: tiga percobaan, jeda naik. Kalau tetap gagal, dicatat
    // sebagai gagal — bukan dianggap terkirim.
    for (let n = 1; n <= 3; n += 1) {
      hasil.percobaan = n;
      try {
        const r = await fetch(l.url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Sab-Signature': `t=${waktu},v1=${sig}`,
            'X-Sab-Event': kejadian.tipe,
            'X-Sab-Event-Id': kejadian.id,
            // Penerima memakai ini untuk membuang kiriman ganda.
            'Idempotency-Key': kejadian.id,
          },
          body: badan,
          signal: AbortSignal.timeout(5000),
        });
        hasil.status = r.status;
        if (r.status >= 200 && r.status < 300) break;
      } catch (e) {
        hasil.status = 0;
        hasil.galat = e.message;
      }
      await new Promise((r) => setTimeout(r, 200 * n));
    }
    db.pengiriman.push(hasil);
  }
  simpan();
}

let noKejadian = 0;
function beritahu(tipe, k) {
  noKejadian += 1;
  const kejadian = {
    id: `evt_${Date.now()}_${noKejadian}`,
    tipe,
    pada: new Date().toISOString(),
    data: publik(k),
  };
  // Sengaja tidak ditunggu: pengirim tidak boleh tertahan oleh penerima.
  kirimWebhook(kejadian).catch(() => {});
  return kejadian;
}

// ---------------------------------------------------------------------------
// Rute
// ---------------------------------------------------------------------------

const rute = [];
function daftar(metode, pola, fn) {
  rute.push({ metode, pola, fn });
}

daftar('GET', /^\/health$/, async (req, res) => {
  kirim(res, 200, {
    status: 'ok',
    seq: db.seq,
    kontak: Object.keys(db.kontak).length,
    konflik_terbuka: Object.keys(db.konflik).length,
  });
});

/** Delta pull. Kursor bilangan urut, bukan waktu. */
daftar('GET', /^\/v1\/contacts$/, async (req, res, q) => {
  const sejak = Number(q.get('since') || 0);
  const batas = Math.min(Number(q.get('limit') || 100), 1000);
  const semua = Object.values(db.kontak)
    .filter((k) => k.seq > sejak)
    .sort((a, b) => a.seq - b.seq);
  const potong = semua.slice(0, batas);
  kirim(res, 200, {
    data: potong.map(publik),
    next_since: potong.length ? potong[potong.length - 1].seq : sejak,
    ada_lagi: semua.length > potong.length,
  });
});

daftar('GET', /^\/v1\/contacts\/([^/]+)$/, async (req, res, q, [id]) => {
  const k = db.kontak[id];
  if (!k) return salah(res, 404, 'tidak_ada', `kontak ${id} tidak ada`);
  kirim(res, 200, publik(k), { ETag: etag(k) });
});

/**
 * Buat kontak. Wajib Idempotency-Key.
 * Kunci yang sama dengan isi yang sama -> 200 dan kontak yang sama, bukan 409
 * dan bukan kontak kedua. Itu inti idempotensi: percobaan ulang harus aman.
 */
daftar('POST', /^\/v1\/contacts$/, async (req, res, q, _p, body) => {
  const kunci = req.headers['idempotency-key'];
  if (!kunci) {
    return salah(res, 428, 'kunci_diperlukan',
      'header Idempotency-Key wajib ada supaya percobaan ulang tidak membuat kontak ganda');
  }
  if (db.idempoten[kunci]) {
    const lama = db.idempoten[kunci];
    return kirim(res, lama.status, lama.body, { 'Idempotent-Replay': 'true' });
  }

  const id = String(body.id || '').trim();
  if (!id) return salah(res, 400, 'id_kosong', 'field id wajib ada');
  if (db.kontak[id]) return salah(res, 409, 'sudah_ada', `kontak ${id} sudah ada`);

  const field = { ...body };
  delete field.id;
  delete field.versi;
  delete field.seq;
  delete field.dihapus;

  const k = { id, versi: 1, seq: 0, dihapus: false, field, updated_at: body.updated_at || null };
  k.seq = catat('buat', id, null, null, null, body.aktor || 'api');
  db.kontak[id] = k;

  const isi = publik(k);
  db.idempoten[kunci] = { status: 201, body: isi, pada: new Date().toISOString() };
  simpan();
  beritahu('kontak.dibuat', k);
  kirim(res, 201, isi, { ETag: etag(k) });
});

/**
 * Ubah kontak — per field, dengan nenek moyang bersama.
 *
 * Isi: { base: {field: nilai_yang_dipegang_klien}, set: {field: nilai_baru} }
 *
 * Untuk setiap field di `set`:
 *   nilai sekarang == base   -> diterapkan (tidak ada yang berubah di sisi lain)
 *   nilai sekarang != base   -> KONFLIK: field itu TIDAK diubah, dicatat
 *
 * Field yang berkonflik dibiarkan apa adanya, field lain tetap diterapkan.
 * Itu janji "field yang tidak berkonflik tetap tersinkron", dan di sini janji
 * itu dipenuhi oleh server, bukan oleh klien yang berharap-harap.
 *
 * If-Match wajib kalau `base` tidak dikirim. Dua cara memeriksa versi, satu
 * aturan: jangan menulis di atas keadaan yang tidak kamu lihat.
 */
daftar('PATCH', /^\/v1\/contacts\/([^/]+)$/, async (req, res, q, [id], body) => {
  const k = db.kontak[id];
  if (!k) return salah(res, 404, 'tidak_ada', `kontak ${id} tidak ada`);

  const ifMatch = req.headers['if-match'];
  if (ifMatch && ifMatch !== etag(k) && ifMatch !== '*') {
    return salah(res, 412, 'versi_basi',
      'ETag tidak cocok: kontak sudah berubah sejak Anda membacanya',
      { etag_sekarang: etag(k), versi_sekarang: k.versi });
  }
  if (!body.base && !ifMatch) {
    return salah(res, 428, 'prasyarat_kurang',
      'kirim `base` (nilai yang Anda pegang) atau header If-Match');
  }

  const base = body.base || {};
  const set = body.set || {};
  const diterapkan = [];
  const bentrok = [];

  // Diubah di satu sisi, dihapus di sisi lain. Menghapus berarti membuang
  // perubahan yang belum tersalin; mengabaikan penghapusan berarti
  // membangkitkan data yang sudah diminta hilang. Keduanya keputusan yang
  // punya akibat, jadi tidak diputuskan mesin: kontak dihidupkan kembali,
  // perubahannya diterapkan, dan keputusan akhirnya masuk antrean.
  if (k.dihapus) {
    k.dihapus = false;
    k.versi += 1;
    catat('pulihkan', id, null, 'dihapus', 'hidup', body.aktor || 'api');
    db.konflik[`${id}|(dihapus)`] = {
      id, field: '(dihapus)', dasar: null, sekarang: 'dihapus',
      diusulkan: 'dihidupkan kembali karena ada perubahan',
      pada: new Date().toISOString(),
    };
    bentrok.push({ field: '(dihapus)', dasar: null, sekarang: 'dihapus',
                   diusulkan: 'dihidupkan kembali karena ada perubahan' });
  }

  for (const [f, nilaiBaru] of Object.entries(set)) {
    // `base` yang tidak memuat field ini berarti klien tidak mengaku memegang
    // nilai apa pun untuk field itu — bukan berarti klien memegang null.
    // Bedanya penting: tanpa ini, klien yang lupa mengirim `base` akan
    // menimpa perubahan orang lain tanpa terdeteksi.
    const punyaDasar = Object.prototype.hasOwnProperty.call(base, f);
    const dasar = punyaDasar ? (base[f] ?? null) : undefined;
    const sekarang = k.field[f] ?? null;
    const baru = nilaiBaru ?? null;

    if (punyaDasar && sekarang !== dasar && sekarang !== baru) {
      // Dua sisi mengubah field yang sama dengan nilai berbeda.
      bentrok.push({ field: f, dasar, sekarang, diusulkan: nilaiBaru });
      db.konflik[`${id}|${f}`] = {
        id, field: f, dasar, sekarang, diusulkan: nilaiBaru,
        pada: new Date().toISOString(),
      };
      continue;
    }
    if (sekarang === baru) continue;   // sudah sama: bukan perubahan

    const dari = sekarang;
    k.field[f] = nilaiBaru;
    diterapkan.push({ field: f, dari, ke: nilaiBaru });
    catat('ubah', id, f, dari, nilaiBaru, body.aktor || 'api');
  }

  if (diterapkan.length) {
    k.versi += 1;
    if (body.updated_at) k.updated_at = body.updated_at;
  }
  if (diterapkan.length || k.dihapus === false) k.seq = db.seq;

  simpan();
  if (diterapkan.length) beritahu('kontak.diubah', k);

  const isi = {
    id,
    versi: k.versi,
    diterapkan,
    konflik: bentrok,
    terbuka: Object.keys(db.konflik).filter((x) => x.startsWith(id + '|')).length,
    data: publik(k),
  };
  // 409 kalau ada konflik: klien WAJIB tahu ada yang tidak tersinkron.
  // 200 hanya kalau seluruh perubahan masuk.
  kirim(res, bentrok.length ? 409 : 200, isi, { ETag: etag(k) });
});

/** Hapus lunak. Tombstone tetap muncul di delta feed supaya penghapusan tersebar. */
daftar('DELETE', /^\/v1\/contacts\/([^/]+)$/, async (req, res, q, [id], body) => {
  const k = db.kontak[id];
  if (!k) return salah(res, 404, 'tidak_ada', `kontak ${id} tidak ada`);
  const ifMatch = req.headers['if-match'];
  if (ifMatch && ifMatch !== etag(k)) {
    return salah(res, 412, 'versi_basi', 'ETag tidak cocok', { etag_sekarang: etag(k) });
  }
  if (k.dihapus) return kirim(res, 200, publik(k), { ETag: etag(k) });

  k.dihapus = true;
  k.versi += 1;
  k.seq = catat('hapus', id, null, null, null, body.aktor || 'api');
  simpan();
  beritahu('kontak.dihapus', k);
  kirim(res, 200, publik(k), { ETag: etag(k) });
});

daftar('GET', /^\/v1\/conflicts$/, async (req, res) => {
  kirim(res, 200, { data: Object.values(db.konflik) });
});

/** Manusia memutuskan. Ini satu-satunya jalan keluar dari konflik. */
daftar('POST', /^\/v1\/conflicts\/resolve$/, async (req, res, q, _p, body) => {
  const kunci = `${body.id}|${body.field}`;
  const c = db.konflik[kunci];
  if (!c) return salah(res, 404, 'tidak_ada', `tidak ada konflik terbuka untuk ${kunci}`);
  const k = db.kontak[body.id];
  if (!k) return salah(res, 404, 'tidak_ada', 'kontaknya sudah tidak ada');

  const dari = k.field[body.field] ?? null;
  k.field[body.field] = body.nilai;
  k.versi += 1;
  k.seq = catat('putuskan', body.id, body.field, dari, body.nilai, body.aktor || 'manusia');
  delete db.konflik[kunci];
  simpan();
  beritahu('kontak.diubah', k);
  kirim(res, 200, { id: body.id, field: body.field, nilai: body.nilai, data: publik(k) },
    { ETag: etag(k) });
});

daftar('POST', /^\/v1\/webhooks$/, async (req, res, q, _p, body) => {
  if (!body.url) return salah(res, 400, 'url_kosong', 'field url wajib ada');
  const l = { url: body.url, sejak: new Date().toISOString() };
  db.langganan.push(l);
  simpan();
  kirim(res, 201, { terdaftar: db.langganan.length, ...l });
});

daftar('GET', /^\/v1\/webhooks\/deliveries$/, async (req, res) => {
  kirim(res, 200, { data: db.pengiriman.slice(-100) });
});

daftar('GET', /^\/v1\/audit$/, async (req, res, q) => {
  const sejak = Number(q.get('since') || 0);
  kirim(res, 200, { data: db.audit.filter((a) => a.seq > sejak).slice(-500) });
});

/** Penerima webhook rujukan: memverifikasi tanda tangan dan membuang kiriman ganda. */
daftar('POST', /^\/contoh\/terima$/, async (req, res, q, _p, body, mentah, kepala) => {
  const sig = kepala['x-sab-signature'] || '';
  const m = /^t=(\d+),v1=([0-9a-f]{64})$/.exec(sig);
  if (!m) return salah(res, 401, 'tanda_tangan_hilang', 'header X-Sab-Signature tidak sah');

  const [, waktu, hex] = m;
  if (Date.now() - Number(waktu) > TOLERANSI_WAKTU) {
    return salah(res, 401, 'tanda_tangan_basi',
      'timestamp lebih tua dari 5 menit — kemungkinan putar ulang');
  }
  const harap = tandaTangan(Number(waktu), mentah);
  if (!samaAman(harap, hex)) {
    return salah(res, 401, 'tanda_tangan_salah', 'HMAC tidak cocok');
  }
  const eid = kepala['x-sab-event-id'];
  if (db.masuk.includes(eid)) {
    return kirim(res, 200, { diterima: true, ganda: true });
  }
  db.masuk.push(eid);
  if (db.masuk.length > 500) db.masuk.shift();
  kirim(res, 200, { diterima: true, tipe: body.tipe, id: body.data && body.data.id });
});

// ---------------------------------------------------------------------------
// Server
// ---------------------------------------------------------------------------

muat();

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  const jalur = url.pathname.replace(/\/+$/, '') || '/';

  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Headers',
    'Content-Type, Authorization, X-API-Key, Idempotency-Key, If-Match');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PATCH, DELETE, OPTIONS');
  if (req.method === 'OPTIONS') return kirim(res, 204, undefined);

  // /health dan /contoh/terima terbuka: yang pertama untuk pemantauan,
  // yang kedua karena keasliannya diperiksa tanda tangan, bukan kunci API.
  const terbuka = jalur === '/health' || jalur === '/contoh/terima';
  if (!terbuka) {
    const auth = req.headers.authorization || '';
    const kunci = auth.startsWith('Bearer ')
      ? auth.slice(7)
      : (req.headers['x-api-key'] || '');
    if (!samaAman(kunci, API_KEY)) {
      return salah(res, 401, 'tidak_diizinkan',
        'kunci API tidak sah — kirim header Authorization: Bearer <kunci>');
    }
  }

  const mentah = await new Promise((selesai) => {
    if (req.method === 'GET' || req.method === 'DELETE') return selesai('');
    const c = [];
    req.on('data', (x) => c.push(x));
    req.on('end', () => selesai(Buffer.concat(c).toString('utf8')));
  });

  let body = {};
  if (mentah.trim()) {
    try {
      body = JSON.parse(mentah);
    } catch {
      return salah(res, 400, 'json_tidak_sah', 'isi permintaan bukan JSON yang sah');
    }
  }

  for (const r of rute) {
    if (r.metode !== req.method) continue;
    const m = r.pola.exec(jalur);
    if (!m) continue;
    try {
      return await r.fn(req, res, url.searchParams, m.slice(1), body, mentah, req.headers);
    } catch (e) {
      return salah(res, 500, 'galat_server', e.message);
    }
  }
  salah(res, 404, 'rute_tidak_ada', `${req.method} ${jalur} tidak dikenal`);
});

if (require.main === module) {
  server.listen(PORT, () => {
    console.log(`CRM API siap di http://127.0.0.1:${PORT}`);
    console.log(`  kunci API : ${API_KEY.slice(0, 4)}… (${API_KEY.length} karakter)`);
    console.log(`  basis data: ${DB}`);
    console.log(`  kontak    : ${Object.keys(db.kontak).length}, seq ${db.seq}`);
  });
}

module.exports = { server, db, tandaTangan, etag };
