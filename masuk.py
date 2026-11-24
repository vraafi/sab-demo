"""Halaman /masuk — bukti bahwa kredensial diperiksa sungguhan.

Alasan halaman ini ada: sebuah demo yang semua tombolnya selalu berhasil tidak
membuktikan apa pun. Yang membuktikan adalah ketika sesuatu yang salah
**benar-benar ditolak**. Karena itu kunci di halaman ini dikirim ke CRM, bukan
dibandingkan di dalam peramban — kalau salah, CRM yang menolak, dan halaman
hanya melaporkan penolakan itu.

Kunci yang benar sengaja tidak ditulis di halaman ini. Kalau ditulis, siapa pun
bisa menyalinnya dan pemeriksaannya kembali menjadi pajangan.
"""

HTML = r"""<!DOCTYPE html>
<html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SAB — masuk</title>
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
a.kembali{margin-left:auto;color:var(--redup);text-decoration:none;font-size:13.5px;
  border:1px solid var(--line);border-radius:8px;padding:6px 12px}
a.kembali:hover{color:var(--teks);border-color:#3d4a5c}
main{flex:1 1 auto;display:grid;place-items:center;padding:24px}
.kotak{width:min(620px,100%);background:var(--panel);border:1px solid var(--line);
  border-radius:16px;padding:30px 32px}
h1{margin:0 0 8px;font-size:24px;line-height:1.3}
p.ket{margin:0 0 20px;color:var(--redup);font-size:14px;line-height:1.6}
label{display:block;font-size:12.5px;color:var(--redup);margin:0 0 7px;
  letter-spacing:.03em;text-transform:uppercase}
input{width:100%;background:var(--panel2);color:var(--teks);border:1px solid var(--line);
  border-radius:10px;padding:12px 14px;font:inherit;font-size:16px;
  font-family:ui-monospace,Consolas,monospace;outline:none}
input:focus{border-color:var(--biru)}
.aksi{display:flex;gap:10px;margin-top:16px}
.utama{flex:1;background:var(--biru);color:#06101f;border:0;border-radius:10px;
  padding:13px;font-size:15.5px;font-weight:700;cursor:pointer;font-family:inherit}
.utama:hover{filter:brightness(1.08)}
.utama[disabled]{opacity:.55;cursor:progress}
.salah{background:transparent;border:1px solid var(--line);color:var(--redup);
  border-radius:10px;padding:13px 16px;font-size:13.5px;cursor:pointer;font-family:inherit}
.salah:hover{color:var(--teks);border-color:#3d4a5c}
.vonis{margin-top:20px;padding:14px 17px;border-radius:12px;border:1px solid var(--line);
  font-size:16.5px;font-weight:650;line-height:1.4}
.vonis.ok{background:var(--ok-bg);border-color:#1d5b33;color:#7ee2a0}
.vonis.bad{background:var(--bad-bg);border-color:#6d2226;color:#ff9a94}
.vonis.tunggu{background:var(--panel2);color:var(--redup)}
.rinci{margin-top:12px;font-size:13.5px;color:var(--redup);line-height:1.65}
.rinci b{color:#dbe3ee}
.mono{font-family:ui-monospace,Consolas,monospace;background:var(--panel2);
  padding:2px 6px;border-radius:5px;border:1px solid var(--line);font-size:13px}
</style></head>
<body>

<header>
  <div class="merek"><b>SAB</b> MASUK</div>
  <a class="kembali" href="/siaran">← layar demo</a>
</header>

<main>
  <div class="kotak">
    <h1>Kunci yang salah harus benar-benar ditolak</h1>
    <p class="ket">
      Halaman ini tidak membandingkan kunci di dalam peramban. Kunci yang Anda
      tulis dikirim ke tempat catatan pelanggan (CRM), dan CRM yang memutuskan.
      Kalau kuncinya salah, penolakannya datang dari sana — bukan dari halaman
      ini. Kunci yang benar sengaja tidak ditulis di layar ini.
    </p>

    <label for="kunci">Kunci akses CRM</label>
    <input id="kunci" autocomplete="off" spellcheck="false"
           placeholder="tulis kunci di sini">

    <div class="aksi">
      <button class="utama" id="masuk">Masuk →</button>
      <button class="salah" id="coba-salah">Isi kunci yang salah</button>
    </div>

    <div id="hasil"></div>
  </div>
</main>

<script>
const $ = (s) => document.querySelector(s);
const hasil = $('#hasil');
const tombol = $('#masuk');

$('#coba-salah').addEventListener('click', () => {
  $('#kunci').value = 'kunci-asal-asalan-' + Math.floor(Math.random() * 900 + 100);
  $('#kunci').focus();
});

async function masuk() {
  const kunci = $('#kunci').value.trim();
  if (!kunci) { $('#kunci').focus(); return; }
  tombol.disabled = true;
  hasil.innerHTML = '<div class="vonis tunggu">Memeriksa ke CRM…</div>';

  let d;
  try {
    const r = await fetch('/api/masuk', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({kunci}),
    });
    d = await r.json();
  } catch (e) {
    hasil.innerHTML = `<div class="vonis bad">✕ Tidak bisa memeriksa</div>
      <div class="rinci">${e.message}</div>`;
    tombol.disabled = false;
    return;
  }

  if (d.ok) {
    hasil.innerHTML = `<div class="vonis ok">✓ Diterima CRM — ${d.jumlah} kontak terbaca</div>
      <div class="rinci">CRM menjawab <span class="mono">200</span> untuk kunci ini.
      Artinya kuncinya benar, dan datanya benar-benar dibaca, bukan ditampilkan
      dari contoh yang disimpan di halaman.</div>`;
  } else {
    hasil.innerHTML = `<div class="vonis bad">✕ Ditolak — ${d.http || 'tanpa jawaban'}</div>
      <div class="rinci">${d.galat || 'Kunci tidak diterima.'}<br><br>
      Penolakan ini datang dari CRM, bukan dari halaman. Kalau kuncinya benar,
      jawabannya akan <b>200</b> beserta jumlah kontak.</div>`;
  }
  tombol.disabled = false;
}

tombol.addEventListener('click', masuk);
$('#kunci').addEventListener('keydown', (e) => { if (e.key === 'Enter') masuk(); });
</script>
</body></html>
"""
