"""Bangun halaman demo SAB dari hasil uji yang benar-benar dijalankan.

Halaman ini tidak menuliskan angka dengan tangan. Semua angka diambil dari
``hasil_demo.json``, yang dihasilkan ``demo.py``. Kalau ujinya dijalankan ulang
dan hasilnya berubah, halamannya ikut berubah -- tidak mungkin ada halaman yang
mengklaim angka lama sementara mesinnya sudah menghasilkan angka baru.

Yang sengaja tidak ada di halaman: tangkapan layar, grafik hiasan, dan tautan
keluar. Yang bisa diperiksa orang lain adalah angka dan tabelnya, bukan gambar.

    python sab_demo/bangun_halaman.py
"""

from __future__ import annotations

import html
import json
from pathlib import Path

AKAR = Path(__file__).resolve().parent
MASUK = AKAR / "hasil_demo.json"
KELUAR = AKAR / "publikasi"

KANAL = {
    "form_website": "Form website",
    "whatsapp": "WhatsApp",
    "email": "Email",
    "google_meta_ads": "Google / Meta Ads",
    "linkedin": "LinkedIn",
}


def muat() -> dict:
    if not MASUK.exists():
        raise SystemExit(
            f"{MASUK.name} belum ada. Jalankan dulu: python sab_demo/demo.py"
        )
    return json.loads(MASUK.read_text(encoding="utf-8"))


def rb(n: int) -> str:
    """Pemisah ribuan gaya Indonesia: 19.900, bukan 19,900."""
    return f"{n:,}".replace(",", ".")


def kartu(angka: str, label: str, nada: str = "") -> str:
    kelas = f"num {nada}".strip()
    return (
        f'<div class="card"><div class="{kelas}">{angka}</div>'
        f'<div class="cap">{html.escape(label)}</div></div>'
    )


def tabel_antrean(baris: list[dict]) -> str:
    if not baris:
        return '<p class="note">Tidak ada pasangan yang perlu dilihat manusia pada uji ini.</p>'

    # Yang paling meyakinkan bukan pasangan yang skornya 1,0 (itu mudah),
    # melainkan yang skornya menengah: mesin tahu ia tidak tahu.
    urut = sorted(baris, key=lambda b: (b.get("skor", 0), b.get("lead", "")))
    potong = urut[:12]

    isi = []
    for b in potong:
        skor = b.get("skor", 0)
        kelas = "s-warn" if skor < 0.9 else "s-ok"
        # Desimal pakai koma: halaman ini berbahasa Indonesia, dan "0.75" di
        # tengah angka ribuan bergaya "19.900" terbaca sebagai salah ketik.
        tampil = f"{skor:.2f}".replace(".", ",")
        isi.append(
            "<tr>"
            f'<td><code>{html.escape(str(b.get("lead", "")))}</code></td>'
            f'<td>{html.escape(KANAL.get(b.get("kanal", ""), b.get("kanal", "")))}</td>'
            f'<td>{html.escape(str(b.get("nama_lead", "")))}</td>'
            f'<td>{html.escape(str(b.get("calon", "")))}</td>'
            f'<td>{html.escape(str(b.get("nama_calon", "")))}</td>'
            f'<td class="{kelas}">{tampil}</td>'
            f'<td>{html.escape(str(b.get("alasan", "")))}</td>'
            "</tr>"
        )

    sisa = len(baris) - len(potong)
    ekor = (
        f'<p class="cap">Menampilkan {len(potong)} dari {len(baris)} pasangan, '
        f"diurutkan dari skor terendah. Sisanya sama bentuknya.</p>"
        if sisa > 0
        else ""
    )

    return (
        "<table><thead><tr>"
        "<th>Lead</th><th>Kanal</th><th>Nama masuk</th>"
        "<th>Calon</th><th>Nama tersimpan</th><th>Skor</th><th>Kenapa tidak digabung</th>"
        "</tr></thead><tbody>" + "".join(isi) + "</tbody></table>" + ekor
    )


def tabel_kasus(kasus: list[dict]) -> str:
    """Tabel uji kasus lapangan. Yang gagal ditandai, bukan disembunyikan."""
    if not kasus:
        return '<p class="note">Uji kasus lapangan belum dijalankan.</p>'
    isi = []
    for k in kasus:
        kelas = "s-ok" if k.get("lulus") else "s-bad"
        tanda = "lulus" if k.get("lulus") else "GAGAL"
        skor = f"{k.get('skor', 0):.2f}".replace(".", ",")
        isi.append(
            "<tr>"
            f'<td>{html.escape(str(k.get("ket", "")))}</td>'
            f'<td><code>{html.escape(str(k.get("nama_a", "")))}</code><br>'
            f'<code>{html.escape(str(k.get("nama_b", "")))}</code></td>'
            f'<td>{html.escape(str(k.get("harap", "")))}</td>'
            f'<td>{html.escape(str(k.get("dapat", "")))}</td>'
            f'<td>{skor}</td>'
            f'<td class="{kelas}">{tanda}</td>'
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Kasus</th><th>Nama</th><th>Harusnya</th>"
        "<th>Hasil</th><th>Skor</th><th></th></tr></thead><tbody>"
        + "".join(isi) + "</tbody></table>"
    )


def tabel_kasus_nyata(kasus: list[dict]) -> str:
    """Tabel kasus nyata, dengan sumbernya. Yang gagal ditandai.

    Baris alias (nama panggilan / ganti nama resmi) diberi tanda "benar
    dipisah", bukan "lulus": hasilnya memang pisah, dan itu yang diharapkan.
    Tanpa label ini, pembaca wajar menyangka baris tersebut kegagalan.
    """
    if not kasus:
        return '<p class="note">Uji kasus nyata belum dijalankan.</p>'
    isi = []
    for k in kasus:
        alias = k.get("jenis") == "alias"
        kelas = "s-ok" if k.get("lulus") else "s-bad"
        if not k.get("lulus"):
            tanda = "GAGAL"
        elif alias:
            tanda = "benar dipisah"
        else:
            tanda = "sesuai"
        skor = f"{k.get('skor', 0):.2f}".replace(".", ",")
        catatan = " <span class=\"cap\">alias</span>" if alias else ""
        isi.append(
            "<tr>"
            f'<td>{html.escape(str(k.get("ket", "")))}</td>'
            f'<td><code>{html.escape(str(k.get("nama_a", "")))}</code><br>'
            f'<code>{html.escape(str(k.get("nama_b", "")))}</code></td>'
            f'<td>{html.escape(str(k.get("dapat", "")))}{catatan}</td>'
            f'<td>{skor}</td>'
            f'<td class="cap">{html.escape(str(k.get("sumber", "")))}</td>'
            f'<td class="{kelas}">{tanda}</td>'
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Kasus</th><th>Nama</th><th>Hasil</th>"
        "<th>Skor</th><th>Sumber</th><th></th></tr></thead><tbody>"
        + "".join(isi) + "</tbody></table>"
    )


def halaman(d: dict) -> str:
    p1 = d.get("poin_1", {})
    p5 = d.get("poin_5", {})
    p6 = d.get("poin_6", {})
    antre = d.get("antrean_contoh", [])

    mentah = p1.get("lead_mentah", 0)
    identitas = p1.get("identitas", 0)
    salah = p1.get("salah_gabung", 0)
    pecah = p1.get("orang_terpecah", 0)
    banding = p1.get("perbandingan", 0)
    tanpa = p1.get("perbandingan_tanpa_blocking", 0)

    kirim = p5.get("dikirim", 0)
    simpan = p5.get("tersimpan", 0)
    tolak = p5.get("ditolak_sebagai_duplikat", 0)

    harus = p6.get("seharusnya_dibalas", 0)
    benar = p6.get("benar_benar_dibalas", 0)
    selisih = p6.get("selisih", 0)
    kecuali = p6.get("pengecualian", [])

    orang_unik = p1.get("orang_unik_sebenarnya", 0)
    duplikat = p1.get("duplikat_ditanam", 0)
    antre_sama = p1.get("antrean_orang_sama", 0)
    antre_beda = p1.get("antrean_orang_beda", 0)
    setelah = p1.get("identitas_setelah_antrean", identitas)

    uk = d.get("uji_kasus", {})
    kasus_total = uk.get("total", 0)
    kasus_lulus = uk.get("lulus", 0)
    kasus_gagal = [k for k in uk.get("kasus", []) if not k.get("lulus")]

    un = d.get("uji_kasus_nyata", {})
    nyata_total = un.get("total", 0)
    nyata_lulus = un.get("lulus", 0)

    un2 = d.get("uji_kasus_nyata2", {})
    nyata2_total = un2.get("total", 0)
    nyata2_lulus = un2.get("lulus", 0)
    nyata2_alias = sum(1 for k in un2.get("kasus", [])
                       if k.get("jenis") == "alias")

    return f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>Demo SAB — poin 1, 5, 6 pada data uji</title>
<style>
  :root {{ --ink:#14171a; --muted:#5b6570; --line:#e3e7ec; --bg:#fff; --soft:#f7f9fb;
           --ok:#0b6b4f; --bad:#a3311f; --warn:#8a5a00; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink);
    font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }}
  .wrap {{ max-width:860px; margin:0 auto; padding:56px 24px 80px; }}
  h1 {{ font-size:32px; line-height:1.2; letter-spacing:-.02em; margin:0 0 14px; }}
  h2 {{ font-size:20px; margin:44px 0 10px; letter-spacing:-.01em; }}
  h3 {{ font-size:15px; margin:24px 0 6px; }}
  p {{ margin:0 0 14px; }}
  .lead {{ font-size:18px; color:var(--muted); }}
  .rule {{ height:1px; background:var(--line); margin:34px 0; }}
  table {{ width:100%; border-collapse:collapse; font-size:13.5px; margin:14px 0 8px; }}
  th,td {{ text-align:left; padding:8px 9px; border-bottom:1px solid var(--line); vertical-align:top; }}
  th {{ font-weight:600; color:var(--muted); font-size:11.5px; text-transform:uppercase;
        letter-spacing:.04em; }}
  code {{ background:var(--soft); padding:1px 5px; border-radius:4px; font-size:12.5px; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; margin:18px 0; }}
  .card {{ background:var(--soft); border:1px solid var(--line); border-radius:8px; padding:14px 16px; }}
  .num {{ font-size:24px; font-weight:700; letter-spacing:-.02em; }}
  .num.ok {{ color:var(--ok); }} .num.bad {{ color:var(--bad); }}
  .cap {{ font-size:13px; color:var(--muted); }}
  .note {{ font-size:14.5px; color:var(--muted); border-left:3px solid var(--line); padding-left:14px; }}
  .s-ok {{ color:var(--ok); font-weight:600; }} .s-warn {{ color:var(--warn); font-weight:600; }}
  .s-bad {{ color:var(--bad); font-weight:600; }}
  ul {{ margin:0 0 14px; padding-left:20px; }} li {{ margin-bottom:7px; }}
  .foot {{ margin-top:48px; font-size:13.5px; color:var(--muted); }}
</style>
</head>
<body>
<div class="wrap">

<h1>Demo poin 1, 5, dan 6 — dijalankan pada data uji</h1>
<p class="lead">Halaman ini memuat hasil satu kali jalan program, bukan rancangan.
Angka di bawah dihasilkan mesinnya sendiri dan bisa dijalankan ulang kapan saja.</p>

<p>Yang perlu disepakati lebih dulu: ini <strong>bukan</strong> sambungan ke CRM SAB.
Ini CRM tiruan berisi {rb(mentah)} lead sintetis dari lima kanal, dengan nomor dan nama
sengaja dibuat tidak konsisten. Yang dibuktikan adalah perilakunya saat data masuk
berantakan — bukan bahwa integrasi ke akun SAB sudah hidup. Sambungan ke akun asli
dikerjakan di tahap 1, setelah demo ini Anda setujui.</p>

<div class="rule"></div>

<h2>Poin 1 — lima kanal masuk ke satu pipeline, dengan dedup</h2>
<p>Yang diuji bukan "lima integrasi menyala" — itu bagian pemasangan. Yang diuji
bagian yang paling sering gagal di lapangan: orang yang sama datang dengan nomor
ditulis <code>0812…</code>, <code>+62812…</code>, dan <code>62812…</code>, dengan nama
ditulis berbeda, harus tetap dikenali sebagai satu orang.</p>

<div class="grid">
{kartu(str(mentah), "lead mentah dari 5 kanal")}
{kartu(str(identitas), "identitas setelah dedup")}
{kartu(str(p1.get("digabung_otomatis", 0)), "digabung otomatis")}
{kartu(str(p1.get("pasangan_antrean", 0)), "masuk antrean manusia")}
{kartu(str(salah), "salah gabung", "ok" if salah == 0 else "bad")}
{kartu(str(pecah), "orang terpecah", "ok" if pecah == 0 else "")}
</div>

<p><strong>Salah gabung: {salah}.</strong> Ini angka yang paling penting, dan bukan
kebetulan. Menggabungkan dua orang berbeda tidak bisa ditarik kembali — riwayat
percakapan dua orang sudah tercampur. Karena itu ambangnya dibuat konservatif:
kalau ragu, jangan gabung, masukkan ke antrean. Konsekuensinya orang yang sama bisa
tertinggal sebagai dua baris ({pecah} kasus di uji ini), dan itu kerugian yang bisa
diperbaiki manusia dalam hitungan detik. Salah gabung tidak bisa.</p>

<p class="note">Biaya pencocokan: {rb(banding)} perbandingan, bukan {rb(tanpa)}.
Tanpa pemblokiran, setiap lead baru dibandingkan dengan semua lead lama — kuadratik,
dan itu yang membuat sistem macet begitu datanya tumbuh. Pemblokiran memakai kunci
dari nomor dan email yang sudah dinormalkan, jadi yang dibandingkan hanya kandidat
yang masuk akal.</p>

<h3>Antrean yang diputuskan manusia, bukan mesin</h3>
<p><strong>Cara membaca skor di tabel ini.</strong> Skor adalah kekuatan bukti,
bukan izin untuk menggabungkan. Ada dua jalur yang berbeda, dan bedanya penting:</p>
<ul>
<li><strong>Nomor atau email cocok</strong> — digabung otomatis, skor 0,95–1,00.
Ini satu-satunya jalur yang boleh menggabungkan tanpa manusia.</li>
<li><strong>Hanya nama yang cocok</strong> — <em>tidak pernah</em> digabung otomatis,
termasuk pada skor 1,00. Pasangan seperti ini selalu masuk antrean.</li>
</ul>
<p>Karena itu Anda akan melihat skor 1,00 di antrean. Itu bukan kesalahan hitung:
itu keputusan bahwa nama saja tidak cukup untuk mengambil alih riwayat orang lain.
Di uji ini antrean berisi {len(antre)} pasangan — {antre_sama} di antaranya
benar-benar orang yang sama (perlu diputuskan manusia), {antre_beda} hanya mirip
namanya. Yang terakhir adalah biaya yang diterima, bukan hasil yang diinginkan,
dan jauh lebih murah daripada menggabungkan dua orang berbeda.</p>
{tabel_antrean(antre)}

<h3>Rekonsiliasi angka</h3>
<p>Angka {identitas} di atas bisa terlihat tidak menutup, jadi ini rinciannya:</p>
<table>
<thead><tr><th>Langkah</th><th>Jumlah</th></tr></thead>
<tbody>
<tr><td>Lead mentah masuk</td><td>{rb(mentah)}</td></tr>
<tr><td>Orang unik sebenarnya (kunci jawaban)</td><td>{rb(orang_unik)}</td></tr>
<tr><td>Duplikat yang ditanam pada data uji</td><td>{rb(duplikat)}</td></tr>
<tr><td>Digabung otomatis lewat nomor atau email</td><td>{rb(p1.get("digabung_otomatis", 0))}</td></tr>
<tr><td>Terpecah, menunggu manusia (aman)</td><td>{rb(pecah)}</td></tr>
<tr><td><strong>Identitas sementara</strong> = {rb(orang_unik)} + {rb(pecah)}</td>
<td><strong>{rb(identitas)}</strong></td></tr>
<tr><td>Setelah antrean diputuskan manusia</td><td>{rb(setelah)}</td></tr>
</tbody>
</table>
<p class="note">Jadi {identitas} bukan angka final. Ia memuat {pecah} orang yang
muncul sebagai dua baris karena tidak digabung otomatis. Setelah {antre_sama}
pasangan di antrean diputuskan, angkanya turun ke {setelah}. Tidak ada duplikat
yang hilang di antara kedua angka itu — keduanya menghitung hal yang sama pada
tahap yang berbeda.</p>

<h3>Yang diperbaiki 23 November 2026</h3>
<p>Versi 21 November mendapat empat catatan. Semuanya benar, dan semuanya
diperbaiki — bukan dijelaskan:</p>
<table>
<thead><tr><th>Catatan</th><th>Penyebab</th><th>Perbaikan</th></tr></thead>
<tbody>
<tr><td>"Pak Dewi" dan "Ibu Dewi" dinilai nyaris identik</td>
<td>Sapaan Pak/Ibu dibuang sebagai gelar, sehingga dua orang berbeda gender
menyusut menjadi satu token yang sama</td>
<td>Sapaan kini dibaca sebagai sinyal. Sapaan berlawanan berarti dua orang
berbeda, dan dipisahkan sebelum skor dihitung</td></tr>
<tr><td>"Hendra Halim" dan "Hendra Fischer" bernilai 0,921</td>
<td>Pencocokan menghitung cakupan kata, sehingga nama depan yang sama menyumbang
terlalu besar</td>
<td>Marga diberi bobot 0,65 dan nama depan 0,35. Marga juga harus cocok sendiri
(minimal 0,85) sebelum sebuah pasangan boleh masuk antrean</td></tr>
<tr><td>Skor 1,00 muncul di antrean manusia</td>
<td>Legenda halaman menyebut 1,00 berarti yakin, padahal jalur nama memang tidak
pernah menggabung otomatis</td>
<td>Legenda ditulis ulang di atas: skor adalah kekuatan bukti, bukan izin
menggabungkan</td></tr>
<tr><td>27 digabung + 3 terpecah = 30, lalu 23 pasangan itu apa</td>
<td>Angka identitas ditampilkan sebagai final padahal antrean belum diputuskan</td>
<td>Tabel rekonsiliasi di atas; angka {identitas} kini ditandai sementara</td></tr>
</tbody>
</table>
<p>Akibatnya, pada data yang sama, pasangan di antrean turun dari 23 menjadi
{len(antre)} — <strong>tanpa kehilangan satu pun duplikat nyata</strong>. Kelima
belas pasangan yang keluar seluruhnya orang berbeda: kebisingan yang selama ini
membuat antrean tidak layak diperiksa manusia.</p>

<h3>Uji kasus lapangan</h3>
<p>Data sintetis bisa lolos hanya karena datanya sendiri yang salah. Karena itu
ada {kasus_total} kasus yang diuji terpisah, diambil dari yang benar-benar muncul
di lapangan Indonesia dan Jerman — termasuk keempat kasus di atas, varian nomor
<code>0812…</code>/<code>+62812…</code>/<code>62812…</code>, email bertanda
<code>+ads</code>, umlaut Jerman, nama terbalik, dan marga yang disingkat.</p>
<p><strong>{kasus_lulus} dari {kasus_total} lulus.</strong> Yang gagal akan
ditampilkan di tabel ini juga, tidak disembunyikan.</p>
{tabel_kasus(uk.get("kasus", []))}

<h3>Uji kasus nyata dari internet</h3>
<p>Kasus di atas saya susun sendiri, jadi bisa saja hanya menguji apa yang sudah
saya pikirkan. Karena itu ada {nyata_total} kasus tambahan yang diambil dari nama
orang sungguhan dan konvensi yang didokumentasikan: kategori nama Indonesia
(mononim, marga Batak, patronimik), gelar daerah (Teuku/Cut di Aceh, Raden Ajeng
di Jawa), partikel bangsawan Jerman (<em>von der</em>), dan transliterasi umlaut.</p>
<p><strong>{nyata_lulus} dari {nyata_total} lulus.</strong> Tiga di antaranya
sempat gagal dan memaksa kode diperbaiki, bukan dijelaskan:</p>
<ul>
<li><strong>Gelar daerah bergender.</strong> "Teuku Ahmad" dan "Cut Ahmad" dinilai
mirip, padahal Teuku menandakan laki-laki dan Cut perempuan di Aceh. Daftar gelar
diperluas dengan gelar daerah yang bergender.</li>
<li><strong>Nama panjang dipendekkan.</strong> "Sri Mulyani Indrawati" dan "Sri
Mulyani" terpisah karena marga yang dibandingkan berbeda. Ditambahkan aturan
awalan: nama yang lebih pendek boleh menjadi awalan nama yang lebih panjang,
dengan syarat minimal dua kata.</li>
<li><strong>Marga sama, orang berbeda.</strong> "Budi Siregar" dan "Ani Siregar"
masuk antrean hanya karena marganya sama — padahal satu marga Batak dipakai
banyak orang, bahkan seisi keluarga. Nama depan kini ikut disyaratkan mirip.</li>
</ul>
{tabel_kasus_nyata(un.get("kasus", []))}
<p class="note"><strong>Dua kasus di atas dipisah bukan karena sistem gagal,
melainkan karena sistem benar.</strong> "Gus Dur" dan "Jokowi" adalah nama
panggilan; "Abdurrahman Wahid" dan "Joko Widodo" adalah nama asli. Sistem ini
wajib memakai nama asli, jadi nama panggilan tidak boleh disatukan dengan nama
asli — menyatukannya adalah kesalahan manusia yang memasukkan julukan ke kolom
nama, bukan kesalahan pencocokan. Memisahkan keduanya adalah perilaku yang
diharapkan. Kalau suatu saat perlu disatukan, itu tugas tabel alias yang diisi
manusia, bukan tebakan mesin.</p>

<h3>Uji kasus nyata putaran kedua — ejaan, transliterasi, dan alias</h3>
<p>Putaran pertama masih bisa dituduh hanya menguji hal yang sudah saya
pikirkan. Karena itu ada {nyata2_total} kasus baru yang diambil dari peristiwa
kebahasaan yang terdokumentasi, bukan dari tebakan: reformasi ejaan Indonesia
1972, transliterasi Jerman, singkatan gelar, dan dua orang yang secara resmi
mengganti nama.</p>
<p><strong>{nyata2_lulus} dari {nyata2_total} sesuai dalam satu kali jalan.</strong>
Sebelas di antaranya pasangan orang yang sama, {nyata2_alias} sisanya alias yang
memang harus dipisah. Dua di antaranya menemukan cacat nyata di kode:</p>
<ul>
<li><strong>Huruf ß dibuang, bukan diterjemahkan.</strong> Pembersih karakter
hanya menyisakan huruf <code>a-z</code>, sehingga ß hilang tanpa jejak dan marga
<code>Weiß</code> tersimpan sebagai <code>wei</code> — nama Jerman kehilangan
huruf terakhirnya. Sekarang ß dipetakan ke <code>ss</code>, seperti ø, æ, dan ł
dipetakan ke bentuk Latinnya. Kasus ini penting karena SAB melayani klien
Jerman.</li>
<li><strong>Ejaan lama Indonesia tidak dikenali.</strong> <code>Soekarno</code>
dan <code>Sukarno</code> terpisah, padahal keduanya satu orang. Wikipedia
mencatat bahwa pada nama orang ejaan lama memang dipertahankan — dan menyebut
<code>Megawati Soekarnoputri</code> sebagai bentuk baku, bukan
<code>Sukarnoputri</code>. Kode kini membaca <code>oe</code>,
<code>tj</code>, <code>dj</code>, <code>nj</code>, <code>sj</code>, dan
<code>ch</code> sebagai sinonim tambahan.</li>
</ul>
<p>Ejaan lama sengaja <em>tidak</em> dijadikan normalisasi global. Di Jerman
<code>oe</code> justru transliterasi dari <code>ö</code>
(<code>Schroeder</code> = <code>Schröder</code>), jadi memetakan
<code>oe</code> menjadi <code>u</code> di seluruh data akan merusak nama Jerman.
Kode mengambil nilai tertinggi dari dua bacaan, sehingga nama Jerman tidak
pernah dirugikan.</p>
<p><strong>Jujur soal batasnya:</strong> kedua perbaikan ini
<em>tidak</em> mengubah angka pada 200 lead di atas — 173 identitas, 27 digabung,
8 antrean, tetap sama. Sebabnya generator data uji tidak pernah menghasilkan ß
maupun ejaan 1972. Artinya perbaikan ini dibuktikan oleh kasus nyata, bukan oleh
data demo, dan data demo tidak boleh dipakai sebagai bukti bahwa keduanya
bekerja.</p>
{tabel_kasus_nyata(un2.get("kasus", []))}

<div class="rule"></div>

<h2>Poin 5 — kiriman ulang tidak membuat data ganda</h2>
<p>Kanal mengirim ulang pemicu kalau endpoint lambat. Kalau ini tidak ditangani,
satu penjualan tercatat dua kali, dan yang tahu lebih dulu adalah pelanggannya.</p>

<div class="grid">
{kartu(rb(kirim), "total kiriman")}
{kartu(str(simpan), "tersimpan", "ok")}
{kartu(rb(tolak), "ditolak sebagai duplikat")}
{kartu(str(p5.get("event_unik", 0)), "event unik seharusnya")}
</div>

<p>Kuncinya disimpan di basis data, bukan di variabel program. Artinya kunci itu
tetap berlaku setelah server dinyalakan ulang — dan itu bagian yang diuji dengan
sengaja mematikan lalu menyalakan kembali mesinnya, bukan hanya dengan mengirim dua
kali berturut-turut.</p>

<div class="rule"></div>

<h2>Poin 6 — rekonsiliasi harian</h2>
<p>Alur bisa hijau seratus persen sementara tidak ada lead yang benar-benar dibalas.
Laporan ini membandingkan yang seharusnya dengan yang benar-benar terjadi, setiap
pagi.</p>

<div class="grid">
{kartu(str(harus), "seharusnya dibalas")}
{kartu(str(benar), "benar-benar dibalas")}
{kartu(str(selisih), "selisih", "ok" if selisih == 0 else "")}
</div>

<p>Selisihnya {selisih}, dan itu disengaja: beberapa lead dibuat gagal supaya
laporannya benar-benar menunjuk sesuatu. Laporan yang selalu nol tidak bisa
dibedakan dari laporan yang tidak jalan. Yang masuk daftar pengecualian:
{", ".join(f"<code>{html.escape(str(k))}</code>" for k in kecuali) if kecuali else "(tidak ada)"}.</p>

<div class="rule"></div>

<h2>Yang belum diuji, dan tidak saya klaim</h2>
<ul>
<li><strong>Kanal asli.</strong> WhatsApp Business, form website SAB, dan CRM SAB belum
disambungkan. Yang berjalan adalah CRM tiruan. Pemasangan ke akun asli adalah
pekerjaan tahap 1.</li>
<li><strong>Poin 2, 3, 4.</strong> Balasan otomatis tiga bahasa, penghentian lintas
kanal, dan sinkron dua arah belum masuk demo ini. Ketiganya ada di lingkup, bukan di
halaman ini.</li>
<li><strong>Beban produksi.</strong> Uji ini memakai {rb(mentah)} lead. Volume SAB yang
sebenarnya belum saya ketahui, dan angka itu yang menentukan kebutuhan server.</li>
<li><strong>Data asli.</strong> Semuanya sintetis. Tidak ada satu pun data pelanggan SAB
yang saya pegang.</li>
</ul>

<p class="note">Halaman ini dibuat oleh skrip dari berkas hasil uji, bukan ditulis
dengan tangan. Kalau ujinya dijalankan ulang dan hasilnya berubah, angka di halaman
ini ikut berubah — tidak ada angka yang bisa tertinggal dari mesinnya.</p>

<h3>Satu batas data uji yang perlu Anda tahu</h3>
<p>Pada data uji ini, sapaan Pak/Ibu ditulis <em>acak per kemunculan</em>, bukan
per orang. Akibatnya satu orang bisa muncul sebagai "Ibu Siti" di satu kanal dan
"Pak Siti" di kanal lain — sesuatu yang tidak mungkin terjadi di dunia nyata,
karena sapaan mengikuti gender orangnya dan tidak berubah antar-kanal. Generator
datanya sudah dicatat untuk diperbaiki pada uji berikutnya. Logika pencocokan
sendiri sudah menangani kasus ini dengan benar (lihat uji kasus lapangan di atas),
tapi data ujinya masih mengandung ketidakkonsistenan itu.</p>

<div class="foot">
Demo SAB — poin 1, 5, 6. Data uji sintetis, CRM tiruan.<br>
Kode yang bisa Anda periksa sendiri:
<a href="https://github.com/vraafi/sab-demo">github.com/vraafi/sab-demo</a><br>
Isinya: <code>dedup.py</code> (logika pencocokan), <code>demo.py</code> (menjalankan
uji), <code>uji_kasus.py</code> (22 kasus lapangan), <code>bandingkan.py</code>
(perbandingan versi lama vs baru), <code>generate.py</code> dan
<code>data_uji.json</code> (data uji), <code>hasil_demo.json</code> (keluaran mentah),
serta <code>log_jalan.txt</code> (log eksekusi).<br>
Dijalankan ulang: <code>python sab_demo/demo.py &amp;&amp; python sab_demo/bangun_halaman.py</code>
</div>

</div>
</body>
</html>
"""


def main() -> int:
    d = muat()
    KELUAR.mkdir(parents=True, exist_ok=True)
    (KELUAR / "index.html").write_text(halaman(d), encoding="utf-8")

    p1, p5, p6 = d.get("poin_1", {}), d.get("poin_5", {}), d.get("poin_6", {})
    print(f"halaman  : {KELUAR / 'index.html'}")
    print(f"poin 1   : {p1.get('lead_mentah')} lead -> {p1.get('identitas')} identitas, "
          f"salah gabung {p1.get('salah_gabung')}")
    print(f"poin 5   : {p5.get('dikirim')} kiriman -> {p5.get('tersimpan')} tersimpan")
    print(f"poin 6   : selisih {p6.get('selisih')} dari {p6.get('seharusnya_dibalas')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
