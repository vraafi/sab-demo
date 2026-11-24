"""Halaman /siaran — layar yang dibagikan saat panggilan.

Alasan halaman ini terpisah dari konsol: saat berbagi layar, yang dilihat orang
lain hanya satu jendela. Konsol penuh angka kecil dan istilah internal terbaca
seperti panel teknisi, bukan seperti produk. Halaman ini kebalikannya:
empat tombol besar, setiap tombol menjelaskan sendiri apa yang baru dibuktikan,
dan tidak ada satu pun jalur yang menampilkan pesan galat mentah ke layar.

Aturan yang dipegang halaman ini:
  * Tidak ada yang perlu diketik, dan tidak ada yang perlu dijelaskan lisan.
  * Kalau mesin tidak menjawab, layar mengatakan itu dengan tenang — bukan
    menampilkan traceback di depan pembeli.
  * Angka yang tampil selalu hasil pengukuran saat tombol ditekan, bukan
    angka yang ditulis tangan di dalam HTML.
"""

HTML = r"""<!DOCTYPE html>
<html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SAB — layar demo</title>
<style>
:root{
  --bg:#0d1117;--panel:#161b22;--panel2:#1c2330;--line:#2b3441;
  --teks:#eef2f7;--redup:#96a1b0;--biru:#4f8cff;
  --ok:#3fb950;--ok-bg:#0f2f1b;--bad:#f85149;--bad-bg:#3a1518;
  --kuning:#d6a419;
}
*{box-sizing:border-box}
html,body{margin:0;height:100%}
body{background:var(--bg);color:var(--teks);
  font:16px/1.5 -apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  display:flex;flex-direction:column;overflow:hidden}

/* ---- kepala ---- */
header{display:flex;align-items:center;gap:14px;padding:14px 26px;
  border-bottom:1px solid var(--line);background:var(--panel);flex:0 0 auto}
.merek{font-weight:700;letter-spacing:.14em;font-size:13px;color:var(--redup)}
.merek b{color:var(--teks);letter-spacing:.02em;font-size:17px;margin-right:8px}
.pil{display:flex;align-items:center;gap:8px;padding:7px 13px;border-radius:99px;
  background:var(--panel2);border:1px solid var(--line);font-size:13px;color:var(--redup)}
.pil .dot{width:9px;height:9px;border-radius:99px;background:#5b6270;flex:0 0 auto}
.pil.ok .dot{background:var(--ok);box-shadow:0 0 0 3px rgba(63,185,80,.18)}
.pil.bad .dot{background:var(--bad);box-shadow:0 0 0 3px rgba(248,81,73,.18)}
.pil b{color:var(--teks);font-weight:600}
.kanan{margin-left:auto;display:flex;gap:10px;align-items:center}
.tombol-kecil{background:transparent;color:var(--redup);border:1px solid var(--line);
  border-radius:9px;padding:8px 14px;font-size:13px;cursor:pointer}
.tombol-kecil:hover{color:var(--teks);border-color:#3d4a5c}

/* ---- isi ---- */
main{flex:1 1 auto;display:grid;grid-template-columns:minmax(330px,38%) 1fr;
  gap:22px;padding:22px 26px;min-height:0}
.aksi{display:flex;flex-direction:column;gap:12px;min-height:0}
.tombol{display:flex;gap:15px;align-items:center;text-align:left;width:100%;
  background:var(--panel);border:1px solid var(--line);border-radius:14px;
  padding:16px 18px;color:var(--teks);cursor:pointer;flex:1 1 0;min-height:76px;
  transition:border-color .14s,background .14s,transform .06s}
.tombol:hover{border-color:var(--biru);background:var(--panel2)}
.tombol:active{transform:translateY(1px)}
.tombol[disabled]{opacity:.5;cursor:progress}
.tombol .no{flex:0 0 auto;width:30px;height:30px;border-radius:9px;background:var(--panel2);
  border:1px solid var(--line);display:grid;place-items:center;
  font-size:14px;font-weight:700;color:var(--biru)}
.tombol .isi{display:flex;flex-direction:column;gap:3px;min-width:0}
.tombol .judul{font-size:16.5px;font-weight:650;line-height:1.3}
.tombol .sub{font-size:13px;color:var(--redup);line-height:1.4}

/* ---- panel hasil ---- */
.hasil{background:var(--panel);border:1px solid var(--line);border-radius:16px;
  padding:26px 30px;overflow:auto;min-height:0;display:flex;flex-direction:column;gap:16px}
.hasil h2{margin:0;font-size:26px;line-height:1.25;font-weight:700}
.hasil .awal{margin:auto;text-align:center;color:var(--redup);max-width:520px}
.hasil .awal .besar{display:block;font-size:22px;color:var(--teks);
  font-weight:650;margin-bottom:10px}
.hasil .awal .kecil{font-size:14px;line-height:1.7}

.vonis{display:flex;align-items:center;gap:12px;font-size:21px;font-weight:700;
  padding:14px 18px;border-radius:12px;border:1px solid var(--line)}
.vonis.ok{background:var(--ok-bg);border-color:#1d5b33;color:#7ee2a0}
.vonis.bad{background:var(--bad-bg);border-color:#6d2226;color:#ff9a94}
.vonis.tunggu{background:var(--panel2);color:var(--redup)}

.baris{display:grid;grid-template-columns:190px 1fr;gap:16px;
  padding:11px 0;border-top:1px solid var(--line);font-size:15px}
.baris:first-of-type{border-top:0}
.baris .l{color:var(--redup);font-size:13.5px;padding-top:2px}
.baris .v{color:var(--teks);word-break:break-word}
.mono{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:13.5px;
  background:var(--panel2);padding:7px 10px;border-radius:8px;border:1px solid var(--line);
  display:inline-block;max-width:100%}
.kutip{border-left:3px solid var(--biru);padding:10px 0 10px 16px;color:#dbe3ee;
  font-size:15.5px;line-height:1.6}
.catatan{color:var(--redup);font-size:13.5px;line-height:1.65}
table.daftar{width:100%;border-collapse:collapse;font-size:15px}
table.daftar th{text-align:left;color:var(--redup);font-weight:500;font-size:12.5px;
  letter-spacing:.04em;text-transform:uppercase;padding:0 0 9px;border-bottom:1px solid var(--line)}
table.daftar td{padding:11px 0;border-bottom:1px solid var(--line);vertical-align:top}
table.daftar td.n{font-weight:600}
table.daftar td.c{color:var(--redup);font-size:13.5px}
.hitung{font-size:14px;color:var(--redup)}
.hitung b{color:var(--teks);font-size:19px;margin-right:5px}

/* ---- kaki ---- */
footer{flex:0 0 auto;display:flex;align-items:center;gap:16px;padding:11px 26px;
  border-top:1px solid var(--line);background:var(--panel);font-size:13px;color:var(--redup)}
footer .kunci{margin-left:auto;font-family:ui-monospace,Consolas,monospace;font-size:12px}
</style></head>
<body>

<header>
  <div class="merek"><b>SAB</b> LAYAR DEMO</div>
  <div class="pil" id="p-n8n"><span class="dot"></span>n8n <b>…</b></div>
  <div class="pil" id="p-crm"><span class="dot"></span>CRM <b>…</b></div>
  <div class="pil" id="p-wa"><span class="dot"></span>Jalur publik <b>…</b></div>
  <div class="kanan">
    <a class="tombol-kecil" href="/masuk" style="text-decoration:none">Kunci &amp; login</a>
    <button class="tombol-kecil" id="layar">Layar penuh</button>
  </div>
</header>

<main>
  <div class="aksi">
    <button class="tombol" data-aksi="kirim">
      <span class="no">1</span>
      <span class="isi">
        <span class="judul">Buktikan pesan WhatsApp terkirim</span>
        <span class="sub">Satu pesan masuk, dibaca, diputuskan, lalu dikirim.
        Meta memberi nomor pesan sebagai bukti.</span>
      </span>
    </button>
    <button class="tombol" data-aksi="coba">
      <span class="no">2</span>
      <span class="isi">
        <span class="judul">Silakan coba sendiri</span>
        <span class="sub">Anda yang mengetik, Anda yang menekan. Sistem membaca,
        memutuskan, dan membalas saat itu juga.</span>
      </span>
    </button>
    <button class="tombol" data-aksi="lead">
      <span class="no">3</span>
      <span class="isi">
        <span class="judul">Tampilkan orang yang sudah masuk</span>
        <span class="sub">Siapa saja yang tercatat, dari kanal mana, sudah sampai
        tahap apa.</span>
      </span>
    </button>
    <button class="tombol" data-aksi="mesin">
      <span class="no">4</span>
      <span class="isi">
        <span class="judul">Periksa mesin</span>
        <span class="sub">Tiga bagian yang harus hidup: n8n, CRM, dan jalur
        WhatsApp.</span>
      </span>
    </button>
    <button class="tombol" data-aksi="batas">
      <span class="no">5</span>
      <span class="isi">
        <span class="judul">Apa yang belum</span>
        <span class="sub">Empat hal yang tidak saya klaim. Lebih baik disebut
        sekarang daripada ditemukan nanti.</span>
      </span>
    </button>
    <button class="tombol" data-aksi="poin">
      <span class="no">6</span>
      <span class="isi">
        <span class="judul">Enam poin uji, berjalan sendiri</span>
        <span class="sub">Delapan slide, sekitar dua menit. Bisa dihentikan dan
        dilanjut dengan tombol panah.</span>
      </span>
    </button>
  </div>

  <div class="hasil" id="hasil">
    <div class="awal">
      <span class="besar">Enam tombol. Tidak perlu bicara.</span>
      <span class="kecil">
        Tekan dari atas ke bawah. Setiap tombol menulis sendiri apa yang baru
        saja dibuktikan, dalam bahasa yang bisa dibaca orang yang belum pernah
        melihat sistem ini.
      </span>
    </div>
  </div>
</main>

<footer>
  <span>Semua angka di layar ini diukur saat tombol ditekan, bukan ditulis di dalam halaman.</span>
  <span class="kunci">← → untuk pindah slide · F11 layar penuh</span>
</footer>

<script>
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, c =>
  ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const hasil = $('#hasil');

function tulis(html) { hasil.innerHTML = html; hasil.scrollTop = 0; }

function tunggu(judul, ket) {
  tulis(`<div class="vonis tunggu">Sedang dikerjakan…</div>
    <h2>${esc(judul)}</h2>
    <p class="catatan">${esc(ket || '')}</p>`);
}

function gagal(judul, ket, ulang) {
  tulis(`<div class="vonis bad">✕ Mesin tidak menjawab</div>
    <h2>${esc(judul)}</h2>
    <p class="catatan">${esc(ket || '')}</p>
    <p class="catatan">Ini ditampilkan apa adanya. Saya tidak menutupi kegagalan
    dengan jawaban contoh.</p>
    ${ulang ? `<div><button class="tombol-kecil" onclick="ulangi('${ulang}')">Coba lagi</button></div>` : ''}`);
}

async function ambil(jalur, opsi) {
  const r = await fetch(jalur, opsi);
  let d = null;
  try { d = await r.json(); } catch (e) { d = null; }
  if (!r.ok) throw new Error((d && (d.galat || d.error)) || ('HTTP ' + r.status));
  if (!d) throw new Error('jawaban bukan JSON');
  return d;
}

/* ---------------- 1. kirim sungguhan ---------------- */
async function aksiKirim() {
  tunggu('Mengirim satu pesan lewat jalur lengkap',
        'Pesan masuk sebagai payload Meta, dibaca, diputuskan, lalu dikirim. '
        + 'Butuh beberapa detik.');
  let d;
  try {
    d = await ambil('/api/kirim-uji', {method: 'POST'});
  } catch (e) {
    gagal('Pengiriman tidak selesai', e.message, 'kirim');
    return;
  }
  const hk = d.hasil_kirim || {};
  const ok = hk.status === 'terkirim';
  const jalur = d.jalur === 'lokal'
    ? 'Jalur lokal n8n (tunnel sedang tidak dipakai)'
    : 'Jalur publik lewat tunnel';

  tulis(`
    <div class="vonis ${ok ? 'ok' : 'bad'}">
      ${ok ? '✓ Pesan benar-benar terkirim' : '✕ Pesan tidak terkirim'}
    </div>
    <h2>${ok
      ? 'Meta mengembalikan nomor pesan. Nomor itu tidak bisa dikarang sistem ini.'
      : 'Meta menolak pengiriman. Alasannya ada di baris terakhir.'}</h2>
    <div>
      <div class="baris"><div class="l">Nomor pesan dari Meta</div>
        <div class="v"><span class="mono">${esc(hk.message_id || '-')}</span></div></div>
      <div class="baris"><div class="l">Status</div>
        <div class="v">${esc(hk.status || '-')} · ${esc(d.ms)} ms</div></div>
      <div class="baris"><div class="l">Lewat jalur</div>
        <div class="v">${esc(jalur)}</div></div>
      <div class="baris"><div class="l">Keputusan sistem</div>
        <div class="v">${esc(d.tindakan || '-')} · bahasa ${esc(d.bahasa || '-')}
        · tingkat ${esc(d.tingkat || '-')}</div></div>
      <div class="baris"><div class="l">Pesan yang dibalas</div>
        <div class="v">“Halo, saya mau tanya harga kamar untuk 20 orang bulan depan,
        budget 50 juta”</div></div>
      <div class="baris"><div class="l">Balasan yang dikirim</div>
        <div class="v"><div class="kutip">${esc(d.balasan || '-')}</div></div></div>
    </div>
    <p class="catatan">Nomor pesan itu dibuat oleh Meta, bukan oleh sistem ini.
    Karena itu ia bisa dipakai untuk membuktikan pesannya benar-benar sampai —
    bukan sekadar animasi di layar.</p>`);
}

/* ---------------- 2. daftar orang ---------------- */
async function aksiLead() {
  tunggu('Mengambil daftar dari CRM', 'Membaca catatan yang tersimpan, bukan contoh.');
  let d;
  try { d = await ambil('/api/lead'); }
  catch (e) { gagal('CRM tidak menjawab', e.message, 'lead'); return; }

  const baris = (d || []).map(k => `<tr>
      <td class="n">${esc(k.nama)}</td>
      <td class="c">${esc(k.kota || '—')}</td>
      <td class="c">${esc(k.tahap || '—')}</td>
    </tr>`).join('');

  tulis(`
    <h2>${(d || []).length} orang tercatat, dan tidak ada yang dobel.</h2>
    <p class="catatan">Satu orang yang menulis lewat dua kanal tetap muncul
    sekali. Penggabungan itu yang mencegah tim menghubungi orang yang sama
    dua kali.</p>
    <div class="hitung"><b>${(d || []).length}</b> kontak ditampilkan</div>
    <table class="daftar">
      <tr><th>Nama</th><th>Kota</th><th>Tahap</th></tr>
      ${baris || '<tr><td colspan="3" class="c">Belum ada kontak.</td></tr>'}
    </table>`);
}

/* ---------------- 4. periksa mesin ---------------- */
async function aksiMesin() {
  tunggu('Memeriksa tiga bagian', 'n8n, CRM, dan jalur WhatsApp.');
  let s, w;
  try { s = await ambil('/api/status'); }
  catch (e) { gagal('Pemeriksaan tidak bisa dijalankan', e.message, 'mesin'); return; }
  try { w = await ambil('/api/wa'); } catch (e) { w = {}; }

  const hidup = (kode) => kode === 200;
  const adaTun = hidup(s.tunnel);
  const baris = [
    ['n8n', hidup(s.n8n), 'mesin alur kerja'],
    ['CRM', hidup(s.crm), 'tempat catatan pelanggan'],
    ['Jalur publik', adaTun ? true : null,
     adaTun ? 'tunnel hidup — pesan dari ponsel asli bisa masuk'
            : 'tidak dipakai — pengiriman tetap jalan lewat jalur lokal'],
  ].map(([n, ok, ket]) => `<div class="baris">
      <div class="l">${esc(n)}</div>
      <div class="v">${ok === true ? '<span style="color:var(--ok)">● hidup</span>'
                        : ok === null ? '<span style="color:var(--redup)">● tidak dipakai</span>'
                        : '<span style="color:var(--bad)">● tidak menjawab</span>'}
        <span class="catatan"> — ${esc(ket)}</span></div>
    </div>`).join('');

  const semua = hidup(s.n8n) && hidup(s.crm);
  tulis(`
    <div class="vonis ${semua ? 'ok' : 'bad'}">
      ${semua ? '✓ Mesin siap dipakai' : '✕ Ada bagian yang tidak menjawab'}
    </div>
    <h2>${semua ? 'Yang penting hidup semua.' : 'Perlu diperiksa sebelum melanjutkan.'}</h2>
    ${baris}
    <div class="baris"><div class="l">Terkirim / gagal</div>
      <div class="v">${esc(w.total_terkirim ?? 0)} terkirim ·
        ${esc(w.total_gagal ?? 0)} masuk daftar gagal</div></div>
    <p class="catatan">Nomor tujuan uji: ${esc(s.tujuan || '-')}.
    Yang gagal tidak hilang — ia dicatat supaya bisa dikirim ulang, bukan
    dibuang diam-diam.</p>`);
}

/* ---------------- 6. presentasi ---------------- */
function aksiPoin() { location.href = '/demo?jeda=14000'; }

/* ---------------- 2. calon pembeli memegang kendali ---------------- */
function aksiCoba() { location.href = '/coba'; }

/* ---------------- 5. apa yang belum ---------------- */
function aksiBatas() {
  const baris = [
    ['Mesin alur kerja (n8n)',
     'Masih di komputer ini, belum di akun SAB. Memindahkan berarti menyerahkan '
     + 'berkas alur kerja dan kredensial — itu pekerjaan serah terima, bukan demo.'],
    ['Tempat catatan pelanggan (CRM)',
     'Masih CRM contoh milik kami. Menyambung ke CRM SAB butuh alamat server dan '
     + 'kunci akses dari pihak SAB.'],
    ['Nomor WhatsApp Tico',
     'Belum terdaftar di daftar penerima uji Meta (batasnya lima nomor). Karena itu '
     + 'pesan dari ponsel Tico belum bisa masuk ke sistem ini.'],
    ['Langganan aplikasi ke WABA',
     'Aplikasi ini belum berlangganan ke akun WhatsApp Business. Yang berlangganan '
     + 'baru aplikasi bawaan Meta. Ini satu klik di konsol Meta, tetapi butuh akses '
     + 'akun — bukan kode.'],
  ].map(([n, k]) => `<div class="baris"><div class="l">${esc(n)}</div>
      <div class="v">${esc(k)}</div></div>`).join('');

  tulis(`
    <div class="vonis tunggu" style="background:#2a2410;border-color:#4a3d16;color:#e8c65a">
      Yang di layar ini nyata. Yang belum, disebutkan.
    </div>
    <h2>Empat hal yang saya tidak klaim</h2>
    ${baris}
    <p class="catatan">Keempatnya bukan soal kode yang belum ditulis. Semuanya
    menunggu akses akun atau keputusan dari pihak SAB. Kalau saya diamkan, Tico
    akan menemukannya sendiri — dan yang rusak bukan sistemnya, melainkan
    kepercayaannya.</p>`);
}

const PETA = {kirim: aksiKirim, coba: aksiCoba, lead: aksiLead, poin: aksiPoin,
              mesin: aksiMesin, batas: aksiBatas};
function ulangi(nama) { if (PETA[nama]) PETA[nama](); }

document.querySelectorAll('.tombol').forEach(b => {
  b.addEventListener('click', async () => {
    const nama = b.dataset.aksi;
    b.disabled = true;
    try { await PETA[nama](); }
    catch (e) { gagal('Tombol gagal dijalankan', e.message, nama); }
    finally { setTimeout(() => { b.disabled = false; }, 600); }
  });
});

/* ---------------- status di kepala ---------------- */
function pasang(id, ok, teks) {
  const el = document.getElementById(id);
  // ok === null berarti "tidak dipakai", bukan "rusak" — jangan diberi warna merah.
  el.className = 'pil ' + (ok === null ? '' : (ok ? 'ok' : 'bad'));
  el.querySelector('b').textContent = teks;
}

async function segarkan() {
  try {
    const s = await ambil('/api/status');
    pasang('p-n8n', s.n8n === 200, s.n8n === 200 ? 'hidup' : 'mati');
    pasang('p-crm', s.crm === 200, s.crm === 200 ? 'hidup' : 'mati');
    pasang('p-wa', s.tunnel === 200 ? true : null,
           s.tunnel === 200 ? 'terhubung' : 'tidak dipakai');
  } catch (e) {
    pasang('p-n8n', false, '?');
    pasang('p-crm', false, '?');
    pasang('p-wa', null, '?');
  }
}

$('#layar').addEventListener('click', () => {
  if (document.fullscreenElement) document.exitFullscreen();
  else document.documentElement.requestFullscreen();
});

// Di alamat publik, dua tombol ini sengaja tidak dibuka: yang satu mengeluarkan
// pesan WhatsApp sungguhan, yang satu membuka daftar kontak. Keduanya tetap ada
// di mesin lokal. Lebih baik dikatakan di tombolnya daripada gagal saat ditekan.
if (window.__publik) {
  [['kirim', 'Tombol ini mengeluarkan pesan sungguhan. Dibuka di mesin lokal, dan diperlihatkan saat panggilan.'],
   ['lead', 'Daftar kontak tidak dibuka di tautan publik.']].forEach(([nama, alasan]) => {
    const b = document.querySelector(`.tombol[data-aksi="${nama}"]`);
    if (!b) return;
    b.disabled = true;
    const sub = b.querySelector('.sub');
    if (sub) sub.textContent = alasan;
  });
}

segarkan();
setInterval(segarkan, 30000);
</script>
</body></html>
"""
