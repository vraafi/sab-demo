"""Halaman /coba — satu-satunya bagian demo yang dipegang calon pembeli.

Celah yang ditemukan dari pembandingan dengan alat demo yang dijual di pasar:
tujuh dari delapan produk semacam itu inti jualannya adalah demo yang bisa
diklik sendiri oleh calon pembeli. Demo yang hanya bisa ditonton menempatkan
pembeli sebagai penonton, dan penonton selalu boleh ragu.

Halaman ini menutup celah itu dengan satu pekerjaan saja: orang mengetik pesan,
lalu melihat sendiri apa yang sistem lakukan terhadap pesannya.

Batas kejujuran yang dipegang:
  * Pintu masuknya formulir, bukan WhatsApp. Itu dikatakan di halaman, bukan
    disembunyikan — karena aplikasi ini belum berlangganan ke WABA.
  * Sesudah pintu masuk, jalurnya sama persis dengan pesan sungguhan.
  * Ada anggaran kirim 5 pesan per 10 menit supaya orang yang menekan tombol
    berkali-kali tidak membanjiri nomor tujuan.
"""

HTML = r"""<!DOCTYPE html>
<html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SAB — coba sendiri</title>
<style>
:root{
  --bg:#0d1117;--panel:#161b22;--panel2:#1c2330;--line:#2b3441;
  --teks:#eef2f7;--redup:#96a1b0;--biru:#4f8cff;
  --ok:#3fb950;--ok-bg:#0f2f1b;--bad:#f85149;--bad-bg:#3a1518;--kuning:#d6a419;
}
*{box-sizing:border-box}
html,body{margin:0;height:100%}
body{background:var(--bg);color:var(--teks);
  font:16px/1.55 -apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  display:flex;flex-direction:column;overflow:hidden}
header{display:flex;align-items:center;gap:14px;padding:13px 26px;
  border-bottom:1px solid var(--line);background:var(--panel);flex:0 0 auto}
.merek{font-size:13px;letter-spacing:.14em;color:var(--redup)}
.merek b{color:var(--teks);letter-spacing:.02em;font-size:17px;margin-right:8px}
a.kembali{color:var(--redup);text-decoration:none;font-size:13.5px;
  border:1px solid var(--line);border-radius:8px;padding:6px 12px}
a.kembali:hover{color:var(--teks);border-color:#3d4a5c}
.kanan{margin-left:auto;display:flex;align-items:center;gap:14px}
.jatah{font-size:13px;color:var(--redup)}
.jatah b{color:var(--teks);font-size:16px}
main{flex:1 1 auto;display:grid;grid-template-columns:minmax(380px,44%) 1fr;
  gap:22px;padding:22px 26px;min-height:0}

/* ---- kolom kiri ---- */
.kiri{display:flex;flex-direction:column;gap:14px;min-height:0}
.kartu{background:var(--panel);border:1px solid var(--line);border-radius:16px;
  padding:20px 22px}
.kartu h2{margin:0 0 4px;font-size:19px;font-weight:650}
.kartu p{margin:0 0 14px;color:var(--redup);font-size:13.5px;line-height:1.55}
label{display:block;font-size:12.5px;color:var(--redup);margin:0 0 6px;
  letter-spacing:.03em;text-transform:uppercase}
input,textarea{width:100%;background:var(--panel2);color:var(--teks);
  border:1px solid var(--line);border-radius:10px;padding:11px 13px;
  font:inherit;font-size:15px;outline:none}
input:focus,textarea:focus{border-color:var(--biru)}
textarea{resize:none;height:104px;line-height:1.5}
.baris-isian{display:flex;flex-direction:column;gap:12px}
.contoh{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 14px}
.contoh button{background:var(--panel2);border:1px solid var(--line);color:var(--redup);
  border-radius:8px;padding:7px 11px;font-size:12.5px;cursor:pointer;font-family:inherit}
.contoh button:hover{color:var(--teks);border-color:var(--biru)}
.kirim{width:100%;margin-top:14px;background:var(--biru);color:#06101f;border:0;
  border-radius:11px;padding:14px;font-size:16px;font-weight:700;cursor:pointer;
  font-family:inherit}
.kirim:hover{filter:brightness(1.08)}
.kirim[disabled]{opacity:.55;cursor:progress}
.catatan-kecil{font-size:12.5px;color:var(--redup);line-height:1.6;
  margin:20px 0 0;padding-top:16px;border-top:1px solid var(--line)}
.catatan-kecil b{color:#dbe3ee}

/* ---- kolom kanan ---- */
.hasil{background:var(--panel);border:1px solid var(--line);border-radius:16px;
  padding:24px 28px;overflow:auto;min-height:0;display:flex;flex-direction:column;gap:14px}
.awal{margin:auto;text-align:center;color:var(--redup);max-width:460px}
.awal .besar{display:block;font-size:21px;color:var(--teks);font-weight:650;margin-bottom:10px}
.awal .kecil{font-size:14px;line-height:1.7}
.vonis{display:flex;align-items:center;gap:11px;font-size:19px;font-weight:700;
  padding:13px 17px;border-radius:12px;border:1px solid var(--line)}
.vonis.ok{background:var(--ok-bg);border-color:#1d5b33;color:#7ee2a0}
.vonis.bad{background:var(--bad-bg);border-color:#6d2226;color:#ff9a94}
.vonis.tunggu{background:var(--panel2);color:var(--redup)}
.vonis.hemat{background:#2a2410;border-color:#4a3d16;color:#e8c65a}
h3{margin:0;font-size:22px;line-height:1.3;font-weight:700}
.baris{display:grid;grid-template-columns:170px 1fr;gap:14px;padding:10px 0;
  border-top:1px solid var(--line);font-size:14.5px}
.baris:first-of-type{border-top:0}
.baris .l{color:var(--redup);font-size:13px;padding-top:2px}
.baris .v{word-break:break-word}
.mono{font-family:ui-monospace,Consolas,monospace;font-size:12.5px;
  background:var(--panel2);padding:6px 9px;border-radius:7px;
  border:1px solid var(--line);display:block;max-width:100%;
  word-break:break-all;white-space:normal;line-height:1.5}
.kutip{border-left:3px solid var(--biru);padding:9px 0 9px 15px;
  color:#dbe3ee;font-size:15.5px;line-height:1.6}
.kecil2{color:var(--redup);font-size:13px;line-height:1.6}
</style></head>
<body>

<header>
  <div class="merek"><b>SAB</b> COBA SENDIRI</div>
  <div class="kanan">
    <span class="jatah">jatah kirim <b id="jatah">5</b> / 5</span>
    <a class="kembali" href="/siaran">← layar demo</a>
  </div>
</header>

<main>
  <div class="kiri">
    <div class="kartu">
      <h2>Tulis seolah Anda calon pembeli</h2>
      <p>Sistem akan membaca pesan Anda, mengenali bahasanya, memutuskan apa yang
      harus dilakukan, lalu menyusun balasan. Semuanya berjalan sekarang, bukan
      contoh yang sudah disiapkan.</p>

      <div class="contoh">
        <button data-isi="Halo, saya butuh 20 kamar untuk bulan depan. Budget 50 juta. Bisa?">Contoh: minta harga</button>
        <button data-isi="Hi, we need 20 rooms next month, budget 50 million. What is the price?">English</button>
        <button data-isi="Guten Tag, wir brauchen 20 Zimmer nächsten Monat. Was kostet das?">Deutsch</button>
      </div>

      <div class="baris-isian">
        <div>
          <label for="nama">Nama Anda</label>
          <input id="nama" value="Tico" maxlength="40" autocomplete="off">
        </div>
        <div>
          <label for="tujuan">Nomor tujuan (kosongkan untuk nomor uji)</label>
          <input id="tujuan" maxlength="20" autocomplete="off" spellcheck="false"
            placeholder="misal 0812xxxxxxx — nomor yang belum terdaftar akan ditolak Meta">
        </div>
        <div>
          <label for="pesan">Pesan</label>
          <textarea id="pesan" maxlength="600"
            placeholder="Halo, saya butuh 20 kamar untuk bulan depan. Budget 50 juta. Bisa?"></textarea>
        </div>
      </div>

      <button class="kirim" id="kirim">Kirim ke sistem →</button>

      <p class="catatan-kecil">
        <b>Yang jujur soal halaman ini:</b> pesan Anda masuk lewat formulir ini,
        bukan dari WhatsApp Anda — aplikasi ini belum berlangganan ke akun
        WhatsApp Business. Tetapi setelah pesan masuk, jalurnya sama persis
        dengan pesan sungguhan: dibaca, dikenali bahasanya, diputuskan, dibalas,
        lalu dikirim. Nomor pesan yang muncul dibuat oleh Meta.
      </p>
    </div>
  </div>

  <div class="hasil" id="hasil">
    <div class="awal">
      <span class="besar">Tidak ada yang disiapkan sebelumnya.</span>
      <span class="kecil">
        Tekan salah satu contoh, atau tulis pesan Anda sendiri, lalu tekan
        “Kirim ke sistem”. Balasannya disusun saat itu juga dari pesan yang
        Anda tulis.
      </span>
    </div>
  </div>
</main>

<script>
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, c =>
  ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const hasil = $('#hasil');
const tombol = $('#kirim');

function tulis(html) { hasil.innerHTML = html; hasil.scrollTop = 0; }

async function ambil(jalur, opsi) {
  const r = await fetch(jalur, opsi);
  let d = null;
  try { d = await r.json(); } catch (e) { d = null; }
  if (!r.ok) throw new Error((d && d.galat) || ('HTTP ' + r.status));
  if (!d) throw new Error('jawaban bukan JSON');
  return d;
}

document.querySelectorAll('.contoh button').forEach(b => {
  b.addEventListener('click', () => {
    $('#pesan').value = b.dataset.isi;
    $('#pesan').focus();
  });
});

async function kirim() {
  const pesan = $('#pesan').value.trim();
  const nama = $('#nama').value.trim() || 'Tamu';
  if (!pesan) { $('#pesan').focus(); return; }

  tombol.disabled = true;
  tulis(`<div class="vonis tunggu">Sedang diproses…</div>
    <h3>Pesan Anda sedang dibaca sistem</h3>
    <p class="kecil2">Bahasa dikenali, keputusan diambil, balasan disusun,
    lalu dikirim. Butuh beberapa detik.</p>`);

  let d;
  try {
    d = await ambil('/api/coba', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({pesan, nama, tujuan: $('#tujuan').value.trim()}),
    });
  } catch (e) {
    tulis(`<div class="vonis bad">✕ Sistem tidak menjawab</div>
      <h3>Pesan Anda tidak sampai ke mesin</h3>
      <p class="kecil2">${esc(e.message)}</p>
      <p class="kecil2">Ini ditampilkan apa adanya. Saya tidak menggantinya
      dengan balasan contoh supaya layar tetap terlihat mulus.</p>`);
    tombol.disabled = false;
    return;
  }

  if (d.tanpa_kirim && !window.__modePublik) {
    // Sekali saja: label jatah diganti, karena di alamat publik tidak ada
    // jatah yang bisa habis — pengirimannya memang tidak dibuka.
    window.__modePublik = true;
    const lbl = document.querySelector('.jatah');
    if (lbl) lbl.innerHTML = 'mode publik · <b>tidak mengirim</b>';
  } else if (d.sisa_kirim !== undefined && !window.__modePublik) {
    $('#jatah').textContent = d.sisa_kirim;
  }

  const hk = d.hasil_kirim || {};
  const gm = d.galat_meta || {};
  const terkirim = d.dikirim === true;
  const ditolakMeta = !terkirim && !!gm.pesan;
  const kelas = terkirim ? 'ok' : (ditolakMeta ? 'bad' : (d.ok ? 'hemat' : 'bad'));
  const judul = terkirim
    ? '✓ Dibaca, diputuskan, dibalas, dan terkirim'
    : ditolakMeta
      ? '✕ Ditolak Meta — bukan oleh sistem ini'
      : (d.ok ? '✓ Dibaca, diputuskan, dibalas — tidak dikirim'
              : '✕ Sistem tidak bisa menyelesaikan pesan ini');

  // Jatah habis hanya berlaku kalau pengiriman memang ditahan karena jatah —
  // bukan kalau Meta yang menolak nomornya, dan bukan kalau ini alamat publik.
  const alasanTidakKirim = (!terkirim && d.ok && !ditolakMeta)
    ? (d.tanpa_kirim
        ? `Ini alamat demo publik. Pesan Anda tetap dibaca, diputuskan, dan
           dibalas penuh — tetapi tidak dikirim ke WhatsApp, supaya tautan yang
           bisa dibuka siapa saja tidak dapat mengeluarkan pesan sungguhan dari
           nomor kami. Pengiriman sungguhan diperlihatkan lewat panggilan.`
        : `Jatah kirim untuk sesi ini habis (${d.jatah_awal} pesan per 10 menit).
           Pesan Anda tetap dibaca dan dibalas penuh — hanya tidak dikirim ke
           WhatsApp, supaya nomor tujuan tidak dibanjiri.`)
    : '';

  tulis(`
    <div class="vonis ${kelas}">${judul}</div>
    <h3>${terkirim
      ? 'Nomor pesan di bawah dibuat oleh Meta, bukan oleh sistem ini.'
      : ditolakMeta
        ? 'Meta menolak nomornya. Kalimat di bawah ditulis Meta, bukan halaman ini.'
        : (d.ok ? 'Isi balasannya nyata. Pengirimannya yang ditahan.'
                : 'Alasannya di bawah.')}</h3>
    <div>
      <div class="baris"><div class="l">Pesan Anda</div>
        <div class="v"><div class="kutip">${esc(d.pesan || pesan)}</div></div></div>
      <div class="baris"><div class="l">Bahasa dikenali</div>
        <div class="v">${esc(d.bahasa || '-')} · dari tulisan, bukan dari nama</div></div>
      <div class="baris"><div class="l">Keputusan</div>
        <div class="v">${esc(d.tindakan || '-')} · tingkat ${esc(d.tingkat || '-')}</div></div>
      <div class="baris"><div class="l">Balasan yang disusun</div>
        <div class="v"><div class="kutip">${esc(d.balasan || '-')}</div></div></div>
      <div class="baris"><div class="l">Status kirim</div>
        <div class="v">${terkirim
          ? `<span style="color:var(--ok)">terkirim</span> · ${esc(d.ms)} ms`
          : `<span style="color:var(--kuning)">tidak dikirim</span>${d.ms ? ' · ' + esc(d.ms) + ' ms' : ''}`}</div></div>
      ${terkirim ? `<div class="baris"><div class="l">Nomor pesan dari Meta</div>
        <div class="v"><span class="mono">${esc(hk.message_id || '-')}</span></div></div>` : ''}
      ${ditolakMeta ? `<div class="baris"><div class="l">Alasan dari Meta</div>
        <div class="v"><span style="color:var(--bad);font-weight:700">#${esc(gm.kode || '?')}</span>
        — ${esc(gm.pesan)}</div></div>` : ''}
      <div class="baris"><div class="l">Lewat jalur</div>
        <div class="v">${esc(d.jalur || '-')}</div></div>
    </div>
    ${alasanTidakKirim ? `<p class="kecil2">${alasanTidakKirim}</p>` : ''}
    ${ditolakMeta ? `<p class="kecil2">Kalimat di atas ditulis Meta, bukan oleh
    halaman ini. Artinya sistem benar-benar mencoba mengirim dan benar-benar
    ditolak. Nomor yang belum terdaftar di daftar penerima uji akan selalu
    ditolak seperti ini — itu batas akun Meta, bukan batas kode.</p>` : ''}
    <p class="kecil2">Coba pesan lain, atau ganti nama Anda — sistem memperlakukan
    setiap nama sebagai orang yang berbeda.</p>`);

  tombol.disabled = false;
}

tombol.addEventListener('click', kirim);
$('#pesan').addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) kirim();
});
</script>
</body></html>
"""
