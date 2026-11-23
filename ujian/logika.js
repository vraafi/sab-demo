/* Logika ujian 50 lead SAB — implementasi JavaScript untuk node Code n8n.
 *
 * Ini port dari mesin.py. Keduanya harus menghasilkan hal yang sama pada data
 * yang sama; itu yang menjawab pertanyaan Tico nomor 7: sistemnya dibangun di
 * n8n, dan Python hanya alat ukur yang dipakai untuk memeriksa hasilnya.
 *
 * Fungsi di bawah sengaja tidak memakai pustaka luar supaya bisa disalin apa
 * adanya ke node Code, yang tidak boleh require modul sembarang.
 */

// ---------------------------------------------------------------- normalisasi

const GELAR_NETRAL = new Set(['dr','drg','ir','prof','drs','dra','st']);
const SAPAAN_L = new Set(['pak','bapak','mas','mr','h','haji','tuan','teuku',
  'teungku','tubagus','cokorda','lalu','datuk','datuak','sutan','tengku']);
const SAPAAN_P = new Set(['bu','ibu','mbak','mrs','ms','hj','hajah','nyonya',
  'nona','cut','baiq','ajeng','rara','nyimas','masayu']);
const SAPAAN = new Set([...SAPAAN_L, ...SAPAAN_P]);

const PETA_HURUF = {'ß':'ss','ẞ':'ss','æ':'ae','Æ':'ae','œ':'oe','Œ':'oe',
  'ø':'o','Ø':'o','đ':'d','Đ':'d','ð':'d','Ð':'d','ł':'l','Ł':'l',
  'þ':'th','Þ':'th'};

function huruf(t) {
  let s = '';
  for (const c of String(t || '')) s += (PETA_HURUF[c] !== undefined ? PETA_HURUF[c] : c);
  // NFKD lalu buang tanda diakritik. Normalisasi bawaan JS menangani ini.
  return s.normalize('NFKD').replace(/[\u0300-\u036f]/g, '');
}

function tokenKasar(n) {
  let s = huruf(String(n || '').toLowerCase());
  s = s.replace(/[^a-z\s.]/g, ' ');
  return s.replace(/\./g, ' ').split(/\s+/).filter(Boolean);
}

function nama(n) {
  return tokenKasar(n).filter(t => !GELAR_NETRAL.has(t) && !SAPAAN.has(t));
}

function telp(s) {
  let d = String(s || '').replace(/\D/g, '');
  if (!d) return '';
  if (d.startsWith('00')) d = d.slice(2);
  if (d.startsWith('0')) d = '62' + d.slice(1);
  else if (d.startsWith('8') && d.length >= 9) d = '62' + d;
  return d;
}

function surel(e) {
  let s = String(e || '').trim().toLowerCase();
  if (!s.includes('@')) return '';
  let [lokal, domain] = [s.slice(0, s.lastIndexOf('@')), s.slice(s.lastIndexOf('@') + 1)];
  lokal = lokal.split('+')[0];
  if (domain === 'gmail.com' || domain === 'googlemail.com') lokal = lokal.replace(/\./g, '');
  return lokal + '@' + domain;
}

// ------------------------------------------------------------------ kemiripan

function jaro(a, b) {
  if (a === b) return 1.0;
  const la = a.length, lb = b.length;
  if (la === 0 || lb === 0) return 0.0;
  const jendela = Math.max(la, lb) / 2 - 1;
  const jw = Math.trunc(jendela);
  const cocokA = new Array(la).fill(false), cocokB = new Array(lb).fill(false);
  let cocok = 0;
  for (let i = 0; i < la; i++) {
    const lo = Math.max(0, i - jw), hi = Math.min(i + jw + 1, lb);
    for (let j = lo; j < hi; j++) {
      if (!cocokB[j] && b[j] === a[i]) { cocokA[i] = cocokB[j] = true; cocok++; break; }
    }
  }
  if (cocok === 0) return 0.0;
  let t = 0, k = 0;
  for (let i = 0; i < la; i++) {
    if (cocokA[i]) {
      while (!cocokB[k]) k++;
      if (a[i] !== b[k]) t++;
      k++;
    }
  }
  t /= 2;
  return (cocok / la + cocok / lb + (cocok - t) / cocok) / 3;
}

function jaroWinkler(a, b) {
  const j = jaro(a, b);
  let p = 0;
  for (let i = 0; i < Math.min(a.length, b.length); i++) {
    if (a[i] === b[i] && p < 4) p++; else break;
  }
  return Math.round((j + p * 0.1 * (1 - j)) * 10000) / 10000;
}

const EJAAN_LAMA = [['oe','u'],['tj','c'],['dj','j'],['sj','sy'],['nj','ny'],['ch','kh']];
function ejaanBaru(t) {
  let s = t;
  for (const [lama, baru] of EJAAN_LAMA) s = s.split(lama).join(baru);
  return s;
}

function miripToken(x, y) {
  if (x === y) return 1.0;
  if (x.length === 1 || y.length === 1) return x[0] === y[0] ? 0.90 : 0.0;
  let skor = jaroWinkler(x, y);
  const ex = ejaanBaru(x), ey = ejaanBaru(y);
  if (ex !== x || ey !== y) skor = Math.max(skor, jaroWinkler(ex, ey));
  return skor;
}

function namaCocok(a, b) {
  const na = nama(a), nb = nama(b);
  if (na.length === 0 || nb.length === 0) return true;
  if (na.some(t => nb.includes(t))) return true;
  if (na.length >= 2 && nb.length >= 2) {
    return miripToken(na[na.length - 1], nb[nb.length - 1]) >= 0.85;
  }
  return miripToken(na[0], nb[0]) >= 0.90;
}

// -------------------------------------------------------------- dedup kanal

class Gabung {
  constructor(n) { this.induk = Array.from({ length: n }, (_, i) => i); }
  cari(i) {
    while (this.induk[i] !== i) { this.induk[i] = this.induk[this.induk[i]]; i = this.induk[i]; }
    return i;
  }
  satukan(a, b) {
    const ra = this.cari(a), rb = this.cari(b);
    if (ra !== rb) this.induk[rb] = ra;
  }
}

function kelompokkan(rows) {
  const n = rows.length;
  const g = new Gabung(n);
  const perTelp = new Map(), perSurel = new Map(), perIsi = new Map();
  const tambah = (m, k, i) => { if (!m.has(k)) m.set(k, []); m.get(k).push(i); };

  rows.forEach((r, i) => {
    r._telp = telp(r.phone);
    r._surel = surel(r.email);
    if (r._telp) tambah(perTelp, r._telp, i);
    if (r._surel) tambah(perSurel, r._surel, i);
    r._sidik = [r.channel, r.name, r.phone, r.email, r.message].join('|');
    tambah(perIsi, r._sidik, i);
  });

  const bentrok = [];
  const sambung = (idx, jenis, nilai) => {
    if (idx.length < 2) return;
    for (let x = 0; x < idx.length; x++) {
      for (let y = x + 1; y < idx.length; y++) {
        const i = idx[x], j = idx[y];
        if (namaCocok(rows[i].name, rows[j].name)) g.satukan(i, j);
        else bentrok.push({
          jenis, nilai, baris_a: rows[i].row_id, nama_a: rows[i].name,
          baris_b: rows[j].row_id, nama_b: rows[j].name,
          sebab: `${jenis} sama tetapi nama tidak cocok — kemungkinan kontak kantor dipakai bersama`,
        });
      }
    }
  };

  for (const [nilai, idx] of perTelp) sambung(idx, 'nomor', nilai);
  for (const [nilai, idx] of perSurel) sambung(idx, 'email', nilai);
  for (const [, idx] of perIsi) {
    if (idx.length > 1) for (const k of idx.slice(1)) g.satukan(idx[0], k);
  }

  const kelompok = new Map();
  for (let i = 0; i < n; i++) {
    const akar = g.cari(i);
    if (!kelompok.has(akar)) kelompok.set(akar, []);
    kelompok.get(akar).push(i);
  }

  const kunciUrut = [...kelompok.entries()].sort((A, B) => {
    const a = rows[Math.min(...A[1])].row_id, b = rows[Math.min(...B[1])].row_id;
    return a < b ? -1 : a > b ? 1 : 0;
  });

  const identitas = [];
  for (const [, idx] of kunciUrut) {
    const anggota = idx.slice().sort((a, b) =>
      rows[a].received_at < rows[b].received_at ? -1 :
      rows[a].received_at > rows[b].received_at ? 1 : 0).map(i => rows[i]);
    const utama = anggota[0];
    const varian = [...new Set(anggota.map(a => a.name))].sort();
    identitas.push({
      id: `SAB-${String(identitas.length + 1).padStart(3, '0')}`,
      nama: utama.name,
      nama_varian: varian,
      telp: (anggota.find(a => a._telp) || {})._telp || '',
      surel: (anggota.find(a => a._surel) || {})._surel || '',
      perusahaan: (anggota.find(a => a.company) || {}).company || '',
      kanal: anggota.map(a => a.channel),
      baris: anggota.map(a => a.row_id),
      pesan: anggota.map(a => a.message),
      pesan_pertama: utama.message,
      waktu_pertama: utama.received_at,
      _anggota: anggota,
    });
  }

  // Kemungkinan duplikat yang hanya bisa dikenali dari nama persis sama.
  const perNama = new Map();
  rows.forEach((r, i) => {
    const tok = nama(r.name);
    if (tok.length >= 2) {
      const k = tok.join(' ');
      if (!perNama.has(k)) perNama.set(k, []);
      perNama.get(k).push(i);
    }
  });
  const mungkin = [];
  for (const [k, idx] of perNama) {
    if (idx.length < 2) continue;
    for (let x = 0; x < idx.length; x++) {
      for (let y = x + 1; y < idx.length; y++) {
        const i = idx[x], j = idx[y];
        if (g.cari(i) === g.cari(j)) continue;
        mungkin.push({
          nama: k, baris_a: rows[i].row_id, baris_b: rows[j].row_id,
          sebab: 'nama persis sama tetapi tidak ada nomor/email yang sama — tidak digabung, menunggu manusia',
        });
      }
    }
  }

  return {
    identitas, bentrok, mungkin,
    stat: {
      baris_masuk: n, identitas: identitas.length,
      digabung: n - identitas.length,
      kontak_dipakai_bersama: bentrok.length,
      kemungkinan_duplikat_nama: mungkin.length,
    },
  };
}

// --------------------------------------------------------------- klasifikasi

const KATA_ID = new Set(['kami','saya','mau','tanya','butuh','bisa','jasa','iklan',
  'untuk','yang','ini','sudah','belum','harga','pasang','minta','bantu','dengan',
  'apakah','dari','kapan','kak','toko','perusahaan','bikin','kirim','info','halo',
  'dan','cuma','jual','murah','kelola','jadwal','penawaran','isi','tadi','besok',
  'tahun','berapa','boleh']);
const KATA_EN = new Set(['we','our','you','your','what','does','looking','for',
  'services','interested','hi','hello','want','expand','follow','include','rates',
  'offer','agencies','more','details','about','sending','partner','package','sales',
  'submission','week','discussed','outbound','into','an']);
const KATA_DE = new Set(['wir','sie','ihr','ihre','ihren','uns','eine','einen',
  'für','können','guten','tag','bitte','keine','weiteren','interesse','an',
  'leistungen','schicken','suchen','agentur','südostasien','angebot','diese',
  'adresse','emails']);

const OPTOUT_ID = [/\bberhenti\b/,/\bstop\b/,/\bjangan (kirim|hubungi|email)\b/,
  /\bunsubscribe\b/,/\bhapus (saya|data)\b/];
const OPTOUT_EN = [/\bunsubscribe\b/,/\bstop\b/,/\bremove me\b/,
  /\bdo(n'?t| not) contact\b/,/\bopt out\b/];
const OPTOUT_DE = [/\bkeine weiteren e-?mails?\b/,/\babmelden\b/,/\baustragen\b/,
  /\bl[öo]schen sie\b/,/\bnicht mehr\b/];
const SPAM = [/\bjual followers\b/,/\bfollowers (murah|cepat)\b/,/\blikes murah\b/,
  /\b10rb followers\b/,/\bjasa followers\b/,/\bpromo followers\b/];

function bahasa(teks) {
  const t = String(teks || '').toLowerCase();
  const kata = new Set((t.match(/[a-zäöüß]+/g) || []));
  const skor = { ID: 0, EN: 0, DE: 0 };
  for (const k of kata) {
    if (KATA_ID.has(k)) skor.ID++;
    if (KATA_EN.has(k)) skor.EN++;
    if (KATA_DE.has(k)) skor.DE++;
  }
  let terbaik = 'ID';
  for (const k of ['EN', 'DE']) if (skor[k] > skor[terbaik]) terbaik = k;
  if (skor[terbaik] === 0) return ['??', skor];
  return [terbaik, skor];
}

function optOut(teks) {
  const t = String(teks || '').toLowerCase();
  return [...OPTOUT_ID, ...OPTOUT_EN, ...OPTOUT_DE].some(p => p.test(t));
}

function spam(teks) {
  const t = String(teks || '').toLowerCase();
  return SPAM.some(p => p.test(t));
}

// ------------------------------------------------------------------ pengiriman

function acak(kunci, garam) {
  // FNV-1a 32-bit. Harus sama persis dengan mesin.py.
  let h = 2166136261 >>> 0;
  const buf = Buffer.from(`${kunci}|${garam}`, 'utf8');
  for (const b of buf) { h = (h ^ b) >>> 0; h = Math.imul(h, 16777619) >>> 0; }
  return h / 4294967296;
}

// Satu kategori kegagalan saja — lihat catatan di mesin.py.
const P_PERMANEN = 0.16;

function tujuanBisa(ident) {
  const kanal = ident.kanal[ident.kanal.length - 1];
  if (kanal === 'whatsapp') return [!!ident.telp, 'nomor'];
  return [!!ident.surel, 'email'];
}

if (typeof module !== 'undefined') {
  module.exports = { huruf, nama, telp, surel, jaro, jaroWinkler, miripToken,
    namaCocok, kelompokkan, bahasa, optOut, spam, acak, tujuanBisa,
    P_PERMANEN };
}
