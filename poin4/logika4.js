// Poin 4 — port JavaScript dari sinkron.py.
//
// Harus menghasilkan keluaran yang PERSIS sama dengan versi Python, karena
// keduanya diuji dengan data yang sama (uji_sama.py). Kalau berbeda satu
// field saja, uji itu gagal. Komentar lengkap soal alasannya ada di sinkron.py;
// di sini hanya aturannya.

const KUNCI = 'id';
const BUKAN_FIELD = new Set([KUNCI, 'versi', 'updated_at']);

function nilai(rec, field) {
  if (!rec) return null;
  const v = rec[field];
  if (v === undefined || v === null || v === '') return null;
  return v;
}

// Perbandingan isi yang tidak bergantung urutan kunci — JSON.stringify
// bergantung urutan, dan itu akan membuat hasil JS berbeda dari Python
// hanya karena urutan field.
function samaIsi(a, b) {
  const fa = [...new Set([...Object.keys(a || {}), ...Object.keys(b || {})])].sort();
  return fa.every(f => (a?.[f] ?? null) === (b?.[f] ?? null));
}

function samaDenganDasar(dasar, sisi) {
  const fields = [...new Set([...Object.keys(dasar || {}), ...Object.keys(sisi || {})])]
    .filter(f => !BUKAN_FIELD.has(f));
  return fields.every(f => nilai(dasar, f) === nilai(sisi, f));
}

function gabungSatu(dasar, lokal, jauh) {
  if (lokal == null && jauh == null) {
    return { hasil: null, konflik: [], catatan: ['tidak ada di kedua sisi'] };
  }

  if (dasar == null) {
    if (lokal != null && jauh == null) {
      return { hasil: { ...lokal }, konflik: [], catatan: ['baru di lokal — dibuat, bukan konflik'] };
    }
    if (jauh != null && lokal == null) {
      return { hasil: { ...jauh }, konflik: [], catatan: ['baru di jauh — dibuat, bukan konflik'] };
    }
    if (samaIsi(lokal, jauh)) {
      return { hasil: { ...lokal }, konflik: [], catatan: ['baru di kedua sisi dengan isi sama'] };
    }
    dasar = {};
  }

  // dihapus di satu sisi
  if (lokal == null && jauh != null) {
    if (samaDenganDasar(dasar, jauh)) {
      return { hasil: null, konflik: [], catatan: ['dihapus di lokal, jauh tidak berubah — dihapus'] };
    }
    return {
      hasil: { ...jauh },
      konflik: [{ id: jauh[KUNCI], field: '*', dasar: '(ada)', lokal: '(dihapus)', jauh: '(diubah)',
        sebab: 'dihapus di lokal tetapi diubah di jauh — penghapusan tidak dijalankan' }],
      catatan: ['hapus-vs-ubah: tidak dihapus, menunggu manusia'],
    };
  }
  if (jauh == null && lokal != null) {
    if (samaDenganDasar(dasar, lokal)) {
      return { hasil: null, konflik: [], catatan: ['dihapus di jauh, lokal tidak berubah — dihapus'] };
    }
    return {
      hasil: { ...lokal },
      konflik: [{ id: lokal[KUNCI], field: '*', dasar: '(ada)', lokal: '(diubah)', jauh: '(dihapus)',
        sebab: 'dihapus di jauh tetapi diubah di lokal — penghapusan tidak dijalankan' }],
      catatan: ['hapus-vs-ubah: tidak dihapus, menunggu manusia'],
    };
  }

  const fields = [...new Set([...Object.keys(dasar), ...Object.keys(lokal), ...Object.keys(jauh)])]
    .filter(f => !BUKAN_FIELD.has(f))
    .sort();

  const hasil = { [KUNCI]: lokal[KUNCI] };
  const konflik = [];
  const catatan = [];
  let adaPerubahan = false;

  for (const f of fields) {
    const d = nilai(dasar, f), l = nilai(lokal, f), j = nilai(jauh, f);

    if (l === j) { hasil[f] = l; continue; }
    if (l === d) { hasil[f] = j; adaPerubahan = true; catatan.push(`${f}: dari jauh`); continue; }
    if (j === d) { hasil[f] = l; adaPerubahan = true; catatan.push(`${f}: dari lokal`); continue; }

    hasil[f] = d;
    konflik.push({
      id: lokal[KUNCI], field: f, dasar: d, lokal: l, jauh: j,
      sebab: 'diubah di dua tempat dengan nilai berbeda',
    });
    catatan.push(`${f}: KONFLIK — dibiarkan pada nilai dasar`);
  }

  let versi = Math.max(lokal.versi || 0, jauh.versi || 0);
  if (adaPerubahan || konflik.length) versi += 1;
  hasil.versi = versi;
  hasil.updated_at = { lokal: lokal.updated_at ?? null, jauh: jauh.updated_at ?? null };
  return { hasil, konflik, catatan };
}

function gabung(data) {
  const peta = (daftar) => {
    const m = new Map();
    for (const r of (daftar || [])) m.set(r[KUNCI], r);
    return m;
  };
  const d = peta(data.dasar), l = peta(data.lokal), j = peta(data.jauh);
  const semua = [...new Set([...d.keys(), ...l.keys(), ...j.keys()])].sort();

  const keluar = [], konflik = [], jejak = [];
  for (const id of semua) {
    const r = gabungSatu(d.get(id) ?? null, l.get(id) ?? null, j.get(id) ?? null);
    if (r.hasil !== null) keluar.push(r.hasil);
    konflik.push(...r.konflik);
    jejak.push({ id, catatan: r.catatan, dihapus: r.hasil === null });
  }

  const pasangan = new Set(konflik.map(k => `${k.id}|${k.field}`));
  return {
    gabung: keluar,
    konflik,
    ringkasan: {
      catatan_dasar: d.size,
      catatan_lokal: l.size,
      catatan_jauh: j.size,
      hasil_gabung: keluar.length,
      konflik: konflik.length,
      konflik_per_field: pasangan.size,
      dihapus: jejak.filter(x => x.dihapus).length,
    },
    jejak,
  };
}

if (typeof module !== 'undefined') {
  module.exports = { gabung, gabungSatu, KUNCI, BUKAN_FIELD };
}
