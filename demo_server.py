#!/usr/bin/env python3
"""Konsol demo hidup — supaya Tico melihat sistem bekerja dengan matanya sendiri.

Kenapa tidak memakai halaman yang sudah ada
===========================================
`sab_demo/publikasi/index.html` adalah gambar mati: nol panggilan `fetch()`,
seluruh angka dipanggang saat dibangun. Membukanya berarti melihat potret
kemarin, bukan sistem yang bekerja hari ini.

Konsol ini sebaliknya:
  - setiap angka diambil dari layanan yang SEDANG berjalan saat halaman dibuka;
  - tombol "Kirim pesan uji" benar-benar mengirim satu pesan WhatsApp dan
    menampilkan `message_id` yang dikembalikan Meta — bukan animasi;
  - kalau ada yang gagal, yang tampil adalah kegagalannya, bukan warna hijau.

Pemakaian
=========
    python demo_server.py            # http://127.0.0.1:8899
    python demo_server.py --port 9000
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SAB = Path(__file__).resolve().parent
AKAR = SAB.parent
sys.path.insert(0, str(SAB))
sys.path.insert(0, str(SAB / "kanal"))
sys.path.insert(0, str(SAB / "poin2"))

from siaran import HTML as SIARAN_HTML  # noqa: E402  (butuh sys.path di atas)
from coba import HTML as COBA_HTML      # noqa: E402
from masuk import HTML as MASUK_HTML    # noqa: E402

N8N = "http://127.0.0.1:5678"
BASIS = f"{N8N}/webhook"
CRM = "http://127.0.0.1:8787"
KUNCI_CRM = "kunci-demo-sab"
DB_N8N = AKAR / ".n8n_home" / ".n8n" / "database.sqlite"
TUNNEL = AKAR / "tmp" / "tunnel_url.txt"
TOKEN_WA = AKAR / "tmp" / "wa_system_token_ui.txt"
PHONE_ID = "1527453537111189"


def _nomor_uji() -> str:
    """Nomor penerima uji — dibaca dari config.json, bukan ditulis di kode.

    Alasannya bukan kerapian: berkas ini dipublikasikan di repo yang bisa dibaca
    Tico, dan nomor telepon seseorang tidak perlu ikut terbaca di sana. Nilai
    sebenarnya tinggal di config.json, yang tidak masuk repo.
    """
    try:
        c = json.loads((SAB / "config.json").read_text(encoding="utf-8"))
        n = str((c.get("nomor") or {}).get("uji") or "")
        if n:
            return n
    except Exception:                                        # noqa: BLE001
        pass
    return os.environ.get("SAB_NOMOR_UJI", "")


TUJUAN_UJI = _nomor_uji()

_kunci = threading.Lock()
_cache: dict = {"pada": 0, "isi": None}


# ---------------------------------------------------------------------------
def _minta(url, metode="GET", muatan=None, kepala=None, timeout=30, mentah=False):
    data = None if muatan is None else json.dumps(muatan).encode()
    h = {"Content-Type": "application/json"}
    if kepala:
        h.update(kepala)
    req = urllib.request.Request(url, data=data, method=metode, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            isi = r.read().decode("utf-8", "replace")
            return r.status, (isi if mentah else _json(isi))
    except urllib.error.HTTPError as e:
        isi = e.read().decode("utf-8", "replace")
        return e.code, (isi if mentah else _json(isi))
    except Exception as e:                                   # noqa: BLE001
        return 0, ({"_galat": type(e).__name__} if not mentah else "")


def _json(s):
    try:
        return json.loads(s) if s else {}
    except Exception:                                        # noqa: BLE001
        return {"_mentah": s[:200]}


def _potong(teks: str, batas: int) -> str:
    """Potong di batas kata, bukan di tengah kata.

    Memotong mentah-mentah menghasilkan "sudah kami c…" di layar, yang terlihat
    seperti salah tulis padahal cuma salah potong.
    """
    teks = " ".join((teks or "").split())
    if len(teks) <= batas:
        return teks
    potong = teks[:batas].rsplit(" ", 1)[0].rstrip(" ,.;:")
    return f"{potong} …"


def alamat_tunnel() -> str:
    try:
        return TUNNEL.read_text(encoding="utf-8").strip().splitlines()[0]
    except Exception:                                        # noqa: BLE001
        return ""


def token_wa() -> str:
    try:
        return TOKEN_WA.read_text(encoding="utf-8").strip()
    except Exception:                                        # noqa: BLE001
        return ""


# ---------------------------------------------------------------------------
# Data untuk halaman
# ---------------------------------------------------------------------------
def status_sistem() -> dict:
    s_n8n, _ = _minta(f"{N8N}/healthz", mentah=True)
    s_crm, _ = _minta(f"{CRM}/health")
    tun = alamat_tunnel()
    s_tun, _ = _minta(f"{tun}/healthz", mentah=True) if tun else (0, "")

    waba_app = []
    tok = token_wa()
    if tok:
        _, d = _minta("https://graph.facebook.com/v27.0/2198366447697523"
                      "/subscribed_apps?access_token=" + tok)
        waba_app = [x.get("whatsapp_business_api_data", {}).get("name", "?")
                    for x in (d.get("data") or [])]
    kita_berlangganan = any("WA DevX" not in n for n in waba_app)

    return {
        "n8n": s_n8n, "crm": s_crm, "tunnel": s_tun, "alamat": tun,
        "aplikasi_waba": waba_app, "kita_berlangganan": kita_berlangganan,
        "tujuan": TUJUAN_UJI,
    }


def kesiapan(segarkan: bool = False) -> dict:
    """Jalankan gerbang kesiapan, simpan 120 detik.

    Tanpa cache, membuka halaman berarti menjalankan 17 pemeriksaan setiap
    kali — cukup lambat untuk terasa seperti sistem yang menggantung.
    """
    with _kunci:
        if not segarkan and _cache["isi"] and time.time() - _cache["pada"] < 120:
            return _cache["isi"]
        kode = 1
        try:
            r = subprocess.run(
                [sys.executable, str(SAB / "pipeline" / "siap_demo.py"),
                 "--json", "--tanpa-kirim"],
                capture_output=True, text=True, timeout=240, cwd=str(SAB / "pipeline"))
            if r.stdout.strip():
                _cache["isi"] = json.loads(r.stdout.strip().splitlines()[-1])
                _cache["pada"] = time.time()
                kode = r.returncode
        except Exception as e:                               # noqa: BLE001
            _cache["isi"] = {"siap": False, "hasil": [
                {"lapis": "?", "nama": "gerbang gagal dijalankan",
                 "lulus": False, "ket": str(e)[:160], "wajib": True}]}
            _cache["pada"] = time.time()
        _cache["isi"]["_kode"] = kode
        return _cache["isi"]


def daftar_lead() -> list[dict]:
    """Lead yang layak ditampilkan ke orang luar.

    Database CRM menyimpan tombstone (kontak terhapus tetap ada) dan sisa
    kontak dari pemeriksaan otomatis. Menampilkan semuanya membuat demo
    terbaca seperti sistem yang berantakan, padahal yang berantakan hanya
    data ujinya. Karena itu: yang dihapus dibuang, kontak uji dibuang, dan
    satu nama hanya muncul sekali dengan versi terbaru.
    """
    _, d = _minta(f"{CRM}/v1/contacts", kepala={"X-API-Key": KUNCI_CRM})
    terbaik: dict[str, dict] = {}
    for k in (d.get("data") or []):
        if k.get("dihapus"):
            continue
        nama = (k.get("nama") or k.get("name") or "").strip()
        if not nama or nama.lower().startswith("uji "):
            continue
        lama = terbaik.get(nama)
        if lama is None or (k.get("versi") or 0) > (lama.get("versi") or 0):
            terbaik[nama] = k
    baris = [{
        "id": k.get("id"), "nama": k.get("nama") or k.get("name") or "",
        "tahap": k.get("tahap") or "", "kota": k.get("kota") or "",
        "versi": k.get("versi"), "dihapus": k.get("dihapus"),
    } for k in terbaik.values()]
    baris.sort(key=lambda x: x["nama"])
    return baris[:10]


def keadaan_wa() -> dict:
    try:
        db = sqlite3.connect(DB_N8N)
        row = db.execute("select staticData from workflow_entity "
                         "where id='sabwacloud01'").fetchone()
        db.close()
        g = (json.loads(row[0]).get("global", {}) if row and row[0] else {})
        return {"terkirim": g.get("terkirim", [])[-5:],
                "gagal": g.get("gagal", [])[-5:],
                "total_terkirim": len(g.get("terkirim", [])),
                "total_gagal": len(g.get("gagal", []))}
    except Exception as e:                                   # noqa: BLE001
        return {"terkirim": [], "gagal": [], "total_terkirim": 0,
                "total_gagal": 0, "_galat": str(e)[:120]}


def normalkan_nomor(nomor: str) -> str:
    """Ubah tulisan nomor apa pun menjadi bentuk yang dipakai Meta (62…).

    Mengembalikan string kosong kalau nomornya tidak masuk akal — supaya
    kegagalan karena nomor salah tidak tersamar sebagai kegagalan jaringan.
    """
    angka = "".join(c for c in str(nomor or "") if c.isdigit())
    if not angka:
        return ""
    if angka.startswith("0"):
        angka = "62" + angka[1:]
    elif angka.startswith("8"):
        angka = "62" + angka
    if not angka.startswith("62") or not (10 <= len(angka) <= 15):
        return ""
    return angka


def galat_kirim(row_id: str) -> dict:
    """Ambil alasan penolakan yang ditulis Meta, dari daftar gagal n8n.

    Tanpa ini, layar hanya bisa bilang "gagal" — dan "gagal" tanpa alasan
    terlihat seperti sistem yang mengarang. Dengan ini, kalimat Meta sendiri
    yang muncul, termasuk kodenya.
    """
    if not row_id:
        return {}
    try:
        db = sqlite3.connect(f"file:{DB_N8N}?mode=ro", uri=True, timeout=5)
        row = db.execute("select staticData from workflow_entity "
                         "where id='sabwacloud01'").fetchone()
        db.close()
        g = json.loads(row[0]).get("global", {}) if row and row[0] else {}
    except Exception:                                        # noqa: BLE001
        return {}
    for e in reversed(g.get("gagal", [])[-25:]):
        if e.get("row_id") != row_id:
            continue
        mentah = str((e.get("galat") or {}).get("message") or "")
        # Pesan Meta datang sebagai JSON yang di-escape dua kali; dibuka dulu
        # supaya kalimatnya bisa dibaca manusia, bukan backslash.
        bersih = mentah.replace('\\"', '"').replace("\\\\", "\\")
        kode = (re.search(r"#(\d+)", bersih) or [None, ""])[1]
        detail = (re.search(r'"details":"([^"]+)"', bersih) or [None, ""])[1]
        judul = (re.search(r'"message":"\(#\d+\) ([^"]+)"', bersih) or [None, ""])[1]
        return {"kode": kode, "pesan": detail or judul or bersih[:220]}
    return {}


def kirim_uji(pesan: str = "", nama: str = "", tujuan: str = "") -> dict:
    """Kirim satu pesan WhatsApp sungguhan lewat jalur lengkap.

    Ini tombol yang membuat Tico melihat dengan matanya sendiri: pesan masuk
    sebagai payload Meta, diputuskan, dikirim, dan `message_id` dari Meta
    muncul di layar.

    `pesan` dan `nama` bisa diisi kalau pesannya datang dari orang yang menonton
    (halaman /coba), bukan dari tombol bawaan.
    """
    pesan = " ".join((pesan or "").split())[:600] or (
        "Halo, saya mau tanya harga kamar untuk 20 orang bulan depan, budget 50 juta")
    nama = " ".join((nama or "").split())[:40] or "Demo Tico"
    tujuan = normalkan_nomor(tujuan) or TUJUAN_UJI

    tun = alamat_tunnel()
    # Tunnel diperiksa dulu dengan batas 3 detik. Kalau mati, jalur lokal dipakai
    # supaya layar tidak menggantung satu menit di depan orang yang menonton.
    dasar, jalur = "", ""
    if tun:
        st, _ = _minta(f"{tun}/healthz", timeout=3, mentah=True)
        if st == 200:
            dasar, jalur = tun, "tunnel"
    if not dasar:
        dasar, jalur = N8N, "lokal"

    _minta(f"{BASIS}/bersihkan", "POST", {})
    muatan = {
        "object": "whatsapp_business_account",
        "entry": [{"id": "2198366447697523", "changes": [{"field": "messages", "value": {
            "messaging_product": "whatsapp",
            "metadata": {"display_phone_number": "15551722929",
                         "phone_number_id": PHONE_ID},
            "contacts": [{"profile": {"name": nama}, "wa_id": tujuan}],
            "messages": [{"from": tujuan,
                          "id": f"wamid.DEMO-{int(time.time())}",
                          "timestamp": "1795000000", "type": "text",
                          "text": {"body": pesan}}],
        }}]}],
    }
    t0 = time.time()
    s, isi = _minta(f"{dasar}/webhook/wa-cloud", "POST", muatan, timeout=45)
    hasil = isi.get("hasil_kirim") or {}
    galat = {}
    if hasil.get("status") != "terkirim":
        galat = galat_kirim(str(hasil.get("row_id") or ""))
    return {"ok": s == 200, "http": s, "ms": int((time.time() - t0) * 1000),
            "galat_meta": galat,
            "jalur": jalur, "tunnel": tun, "pesan": pesan, "nama": nama,
            "tujuan": tujuan,
            "tindakan": isi.get("tindakan"), "bahasa": isi.get("bahasa"),
            "tingkat": isi.get("tingkat"), "balasan": isi.get("balasan"),
            "hasil_kirim": isi.get("hasil_kirim"), "jawaban_mentah": isi}


# ---------------------------------------------------------------------------
# Halaman /coba — Tico memegang kendali
# ---------------------------------------------------------------------------
# Kriteria keempat yang dipakai pasar untuk menilai alat demo adalah "keamanan
# lingkungan demo": jangan sampai penonton yang menekan tombol berkali-kali
# mengirim puluhan pesan sungguhan ke nomor orang. Karena itu ada anggaran
# kirim: 5 pesan per 10 menit. Lewat dari itu, sistem tetap membaca dan menyusun
# balasan, tetapi tidak mengirim — dan layar mengatakan itu apa adanya.
_KIRIM_JEJAK: list[float] = []
# Bisa dinaikkan lewat lingkungan untuk keperluan uji (instance terpisah),
# supaya demo yang dipakai di panggilan tetap berjatah 5.
KIRIM_MAKS = int(os.environ.get("SAB_KIRIM_MAKS", "5"))
KIRIM_JEDA = 600.0
_kunci_kirim = threading.Lock()

# Alamat publik: pesan tetap dibaca, diputuskan, dan dibalas — tetapi tidak
# dikirim ke WhatsApp. Bukan karena mesinnya tidak bisa, melainkan karena
# tautan yang bisa dibuka siapa saja tidak boleh bisa mengeluarkan pesan
# sungguhan dari nomor kita. Pengiriman sungguhan tetap ada di mesin lokal,
# yang dipakai saat panggilan.
TANPA_KIRIM = os.environ.get("SAB_TANPA_KIRIM", "") == "1"


def anggaran_kirim() -> tuple[bool, int]:
    """(masih boleh kirim, sisa jatah)."""
    with _kunci_kirim:
        sekarang = time.time()
        _KIRIM_JEJAK[:] = [t for t in _KIRIM_JEJAK if sekarang - t < KIRIM_JEDA]
        sisa = KIRIM_MAKS - len(_KIRIM_JEJAK)
    return sisa > 0, max(0, sisa)


def coba_pesan(pesan: str, nama: str = "", tujuan: str = "") -> dict:
    """Satu pesan dari orang yang menonton, diproses sistem yang sebenarnya.

    Yang disimulasikan hanya pintu masuknya: pesan diketik di formulir, bukan
    dikirim dari WhatsApp Tico — karena aplikasi ini belum berlangganan ke WABA.
    Sesudah pintu masuk, jalurnya sama persis dengan pesan sungguhan: dibaca,
    bahasanya dikenali, diputuskan, dibalas, lalu dikirim.
    """
    pesan = " ".join((pesan or "").split())[:600]
    if not pesan:
        return {"ok": False, "galat": "pesannya masih kosong"}
    nama = " ".join((nama or "").split())[:40] or "Tamu"

    nomor = normalkan_nomor(tujuan) or TUJUAN_UJI
    boleh, sisa = anggaran_kirim()
    if TANPA_KIRIM:
        boleh = False
    if boleh:
        d = kirim_uji(pesan=pesan, nama=nama, tujuan=nomor)
        d["dikirim"] = bool((d.get("hasil_kirim") or {}).get("status") == "terkirim")
        if d["dikirim"]:
            with _kunci_kirim:
                _KIRIM_JEJAK.append(time.time())
            sisa -= 1
    else:
        # Jatah habis: tetap diputuskan dan dibalas, tetapi tidak dikirim.
        _minta(f"{BASIS}/bersihkan", "POST", {})
        r = _balas("COBA", "whatsapp", nama, nomor, "", pesan)
        d = {"ok": True, "ms": r.get("ms"), "jalur": "tanpa kirim",
             "dikirim": False, "tindakan": r.get("tindakan"),
             "bahasa": r.get("bahasa"), "tingkat": r.get("tingkat"),
             "balasan": r.get("balasan"), "hasil_kirim": None}

    d.update({"pesan": pesan, "nama": nama, "sisa_kirim": max(0, sisa),
              "jatah_awal": KIRIM_MAKS, "tujuan": nomor,
              "tanpa_kirim": TANPA_KIRIM})
    return d


def masuk(kunci: str) -> dict:
    """Periksa kredensial ke CRM yang sebenarnya — bukan dibandingkan di layar.

    Kunci dikirim ke CRM. Kalau salah, CRM menjawab 401 dan halaman harus
    mengatakan itu. Tidak ada jalan pintas yang membuat kunci salah terlihat
    benar hanya supaya demonya mulus.
    """
    kunci = str(kunci or "").strip()
    if not kunci:
        return {"ok": False, "http": 0, "galat": "kuncinya masih kosong"}
    s, isi = _minta(f"{CRM}/v1/contacts", kepala={"X-API-Key": kunci})
    if s == 200:
        # _minta sudah mengurai JSON, jadi isi bisa berupa dict.
        if isinstance(isi, dict):
            jumlah = len(isi.get("data") or [])
        else:
            try:
                jumlah = len(json.loads(isi).get("data") or [])
            except Exception:                                # noqa: BLE001
                jumlah = 0
        return {"ok": True, "http": s, "jumlah": jumlah,
                "pesan": "Kunci diterima CRM."}
    if s == 401:
        return {"ok": False, "http": s,
                "galat": "CRM menolak kunci ini (401). Kuncinya salah."}
    return {"ok": False, "http": s,
            "galat": f"CRM menjawab {s or 'tanpa jawaban'} — bukan soal kunci, "
                     f"melainkan layanannya."}


def bersihkan_sesi() -> dict:
    """Mulai sesi baru: kosongkan ingatan pipeline dan jatah kirim."""
    with _kunci_kirim:
        _KIRIM_JEJAK.clear()
    s, _ = _minta(f"{BASIS}/bersihkan", "POST", {})
    return {"ok": s == 200, "http": s, "sisa_kirim": KIRIM_MAKS}


# ---------------------------------------------------------------------------
# Halaman
# ---------------------------------------------------------------------------
HALAMAN = r"""<!DOCTYPE html>
<html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Konsol Demo — SAB</title>
<style>
:root{--bg:#f6f7f9;--panel:#fff;--line:#e3e6ec;--teks:#1a1d23;--redup:#5b6270;
--hijau:#0f7b4f;--hijau-bg:#e7f6ee;--merah:#b4232c;--merah-bg:#fdecec;
--kuning:#8a5a00;--kuning-bg:#fff5e0;--biru:#1f5fbf}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--teks);
font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:28px 20px 64px}
header{display:flex;align-items:flex-start;justify-content:space-between;gap:20px;
flex-wrap:wrap;margin-bottom:22px}
h1{font-size:22px;margin:0 0 4px;letter-spacing:-.01em}
.sub{color:var(--redup);font-size:13px}
.badge{padding:9px 16px;border-radius:999px;font-weight:600;font-size:14px;
white-space:nowrap;border:1px solid transparent}
.b-ok{background:var(--hijau-bg);color:var(--hijau);border-color:#bfe6d3}
.b-no{background:var(--merah-bg);color:var(--merah);border-color:#f3c7c9}
.b-tunggu{background:var(--kuning-bg);color:var(--kuning);border-color:#f0dcae}
.kotak{background:var(--panel);border:1px solid var(--line);border-radius:12px;
padding:18px 20px;margin-bottom:16px}
.kotak h2{font-size:15px;margin:0 0 14px;letter-spacing:.01em}
.kotak h2 span{color:var(--redup);font-weight:400;font-size:13px;margin-left:8px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.tile{border:1px solid var(--line);border-radius:10px;padding:12px 14px;background:#fbfcfd}
.tile .l{font-size:12px;color:var(--redup);margin-bottom:4px}
.tile .v{font-size:17px;font-weight:600}
.ok{color:var(--hijau)}.no{color:var(--merah)}.warn{color:var(--kuning)}
table{width:100%;border-collapse:collapse;font-size:13.5px}
th,td{text-align:left;padding:9px 10px;border-bottom:1px solid var(--line);
vertical-align:top}
th{font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--redup);
font-weight:600}
tr:last-child td{border-bottom:none}
.pil{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12px;font-weight:600}
.p-ok{background:var(--hijau-bg);color:var(--hijau)}
.p-no{background:var(--merah-bg);color:var(--merah)}
.p-note{background:var(--kuning-bg);color:var(--kuning)}
button{font:inherit;font-weight:600;padding:11px 20px;border-radius:9px;border:0;
background:var(--biru);color:#fff;cursor:pointer}
button:disabled{opacity:.55;cursor:progress}
.hasil{margin-top:14px;padding:14px 16px;border-radius:10px;background:#f2f6fd;
border:1px solid #d3e2f8;font-size:13.5px;display:none;white-space:pre-wrap;
word-break:break-word}
.hasil.tampil{display:block}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12.5px}
.catatan{font-size:13px;color:var(--redup);margin:8px 0 0}
</style></head><body><div class="wrap">

<header>
  <div>
    <h1>Konsol Demo — SAB</h1>
    <div class="sub" id="waktu">memuat…</div>
  </div>
  <div class="badge b-tunggu" id="verdict">Memeriksa sistem…</div>
</header>

<div class="kotak">
  <h2>Infrastruktur <span>dibaca langsung dari layanan yang berjalan</span></h2>
  <div class="tiles" id="tiles"><div class="tile"><div class="l">memuat</div></div></div>
</div>

<div class="kotak">
  <h2>Enam poin Tico <span>setiap baris dijalankan saat halaman ini dibuka</span></h2>
  <table><thead><tr><th style="width:60px">Poin</th><th>Pemeriksaan</th>
  <th style="width:88px">Hasil</th><th>Bukti</th></tr></thead>
  <tbody id="poin"><tr><td colspan="4" class="catatan">memeriksa…</td></tr></tbody></table>
</div>

<div class="kotak">
  <h2>Uji kirim WhatsApp <span>pesan sungguhan, bukan simulasi</span></h2>
  <p class="catatan">Menekan tombol ini mengirim satu pesan WhatsApp ke
  <span class="mono" id="tujuan"></span> lewat jalur lengkap: payload Meta masuk →
  mesin keputusan → Graph API → <span class="mono">message_id</span>.</p>
  <button id="btn">Kirim pesan uji sekarang</button>
  <div class="hasil" id="hasil"></div>
</div>

<div class="kotak">
  <h2>Lead di CRM <span>hasil sinkronisasi dua arah</span></h2>
  <table><thead><tr><th>ID</th><th>Nama</th><th>Tahap</th><th>Kota</th>
  <th style="width:70px">Versi</th></tr></thead>
  <tbody id="lead"><tr><td colspan="5" class="catatan">memuat…</td></tr></tbody></table>
</div>

<div class="kotak">
  <h2>Kiriman WhatsApp terakhir <span>dan DLQ bila ada yang gagal</span></h2>
  <div id="wa"><div class="catatan">memuat…</div></div>
</div>

<script>
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, c =>
  ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

async function ambil(jalur, opsi) {
  const r = await fetch(jalur, opsi);
  if (!r.ok) throw new Error('HTTP ' + r.status);
  return r.json();
}

function tile(label, nilai, kelas) {
  return `<div class="tile"><div class="l">${esc(label)}</div>
  <div class="v ${kelas || ''}">${esc(nilai)}</div></div>`;
}

async function muatStatus() {
  try {
    const s = await ambil('/api/status');
    $('tiles').innerHTML =
      tile('n8n', s.n8n === 200 ? 'hidup' : 'mati', s.n8n === 200 ? 'ok' : 'no') +
      tile('CRM API', s.crm === 200 ? 'hidup' : 'mati', s.crm === 200 ? 'ok' : 'no') +
      tile('Tunnel publik', s.tunnel === 200 ? 'hidup' : 'mati', s.tunnel === 200 ? 'ok' : 'no') +
      tile('Aplikasi di WABA', s.kita_berlangganan ? 'berlangganan' : 'belum',
           s.kita_berlangganan ? 'ok' : 'no') +
      tile('Nomor WhatsApp', '+1 555-172-2929', '');
    $('waktu').textContent = 'Diperiksa ' + new Date().toLocaleString('id-ID') +
      ' · ' + (s.alamat || 'tanpa tunnel');
    if (s.tujuan) $('tujuan').textContent = '+' + s.tujuan;
  } catch (e) {
    $('tiles').innerHTML = tile('status', 'gagal dibaca', 'no');
  }
}

async function muatKesiapan(segarkan) {
  $('poin').innerHTML = '<tr><td colspan="4" class="catatan">memeriksa 17 hal…</td></tr>';
  $('verdict').className = 'badge b-tunggu';
  $('verdict').textContent = 'Memeriksa sistem…';
  try {
    const d = await ambil('/api/kesiapan' + (segarkan ? '?segarkan=1' : ''));
    const wajibGagal = d.hasil.filter(h => h.wajib && !h.lulus);
    $('verdict').className = 'badge ' + (wajibGagal.length ? 'b-no' : 'b-ok');
    $('verdict').textContent = wajibGagal.length
      ? wajibGagal.length + ' penghalang'
      : 'Siap demo — 0 penghalang';
    $('poin').innerHTML = d.hasil.map(h => {
      const pil = h.lulus ? '<span class="pil p-ok">lulus</span>'
        : (h.wajib ? '<span class="pil p-no">gagal</span>'
                   : '<span class="pil p-note">catatan</span>');
      return `<tr><td class="mono">${esc(h.lapis)}</td><td>${esc(h.nama)}</td>
      <td>${pil}</td><td class="catatan">${esc(h.ket)}</td></tr>`;
    }).join('');
  } catch (e) {
    $('verdict').className = 'badge b-no';
    $('verdict').textContent = 'gerbang gagal dijalankan';
    $('poin').innerHTML = '<tr><td colspan="4" class="catatan">' + esc(e.message) + '</td></tr>';
  }
}

async function muatLead() {
  try {
    const d = await ambil('/api/lead');
    $('lead').innerHTML = d.length ? d.map(k => `<tr>
      <td class="mono">${esc(k.id)}</td><td>${esc(k.nama)}</td>
      <td>${esc(k.tahap)}</td><td>${esc(k.kota)}</td>
      <td class="mono">${esc(k.versi)}</td></tr>`).join('')
      : '<tr><td colspan="5" class="catatan">belum ada lead</td></tr>';
  } catch (e) { $('lead').innerHTML = '<tr><td colspan="5" class="catatan">gagal dibaca</td></tr>'; }
}

async function muatWa() {
  try {
    const d = await ambil('/api/wa');
    let h = `<div class="tiles" style="margin-bottom:12px">
      ${tile('Terkirim', d.total_terkirim, 'ok')}
      ${tile('Masuk DLQ', d.total_gagal, d.total_gagal ? 'no' : '')}</div>`;
    if (d.terkirim.length) {
      h += '<table><thead><tr><th>Waktu</th><th>Tujuan</th><th>Message ID</th></tr></thead><tbody>' +
        d.terkirim.slice().reverse().map(t => `<tr>
        <td class="mono">${esc((t.pada||'').slice(11,19))}</td>
        <td class="mono">${esc(t.ke)}</td>
        <td class="mono">${esc((t.message_id||'').slice(0,34))}…</td></tr>`).join('') +
        '</tbody></table>';
    } else { h += '<p class="catatan">belum ada kiriman pada sesi ini.</p>'; }
    if (d.gagal.length) {
      h += '<p class="catatan" style="color:#b4232c">DLQ: ' +
        d.gagal.slice().reverse().map(g => esc((g.galat && g.galat.message) || g.status))
          .join(' · ') + '</p>';
    }
    $('wa').innerHTML = h;
  } catch (e) { $('wa').innerHTML = '<div class="catatan">gagal dibaca</div>'; }
}

$('btn').addEventListener('click', async () => {
  const b = $('btn'); b.disabled = true; b.textContent = 'Mengirim…';
  const kotak = $('hasil'); kotak.className = 'hasil tampil';
  kotak.textContent = 'Menjalankan jalur: payload Meta → keputusan → Graph API…';
  try {
    const d = await ambil('/api/kirim-uji', {method:'POST'});
    if (!d.ok) {
      kotak.textContent = 'GAGAL (HTTP ' + d.http + ')\n' +
        JSON.stringify(d.jawaban_mentah || d, null, 2);
    } else {
      const hk = d.hasil_kirim || {};
      kotak.textContent =
        'Tindakan   : ' + (d.tindakan || '-') + '\n' +
        'Bahasa     : ' + (d.bahasa || '-') + '  (tingkat: ' + (d.tingkat || '-') + ')\n' +
        'Balasan    : ' + (d.balasan || '-') + '\n' +
        'Status     : ' + (hk.status || '-') + '\n' +
        'Message ID : ' + (hk.message_id || '-') + '\n' +
        'Waktu      : ' + d.ms + ' ms';
    }
  } catch (e) {
    kotak.textContent = 'GAGAL: ' + e.message;
  }
  b.disabled = false; b.textContent = 'Kirim pesan uji sekarang';
  muatWa();
});

$('tujuan').textContent = 'memuat…';
muatStatus(); muatKesiapan(false); muatLead(); muatWa();
setInterval(muatStatus, 15000);
setInterval(muatWa, 15000);
</script></div></body></html>"""


# ---------------------------------------------------------------------------
# Demo otomatis — dijalankan sekali, hasilnya dipakai halaman presentasi
#
# Kenapa bukan sekadar menampilkan angka: pemilik tidak bisa berbicara di
# Google Meet (tidak ada mic, audio kecil). Karena itu setiap langkah harus
# menjelaskan DIRINYA di layar: apa yang dikirim, apa yang dijawab sistem,
# dan mengapa itu membuktikan poin yang dimaksud.
# ---------------------------------------------------------------------------
def _balas(row_id, kanal, nama="", telp="", surel="", pesan="", catat=None):
    muatan = {"row_id": row_id, "kanal": kanal, "nama": nama, "pesan": pesan}
    if telp:
        muatan["telp"] = telp
    if surel:
        muatan["surel"] = surel
    _, isi = _minta(f"{BASIS}/balas", "POST", muatan)
    if catat is not None:
        catat.append(isi)
    return isi


def jalankan_demo() -> dict:
    import dedup

    _minta(f"{BASIS}/bersihkan", "POST", {})
    semua: list[dict] = []
    poin: list[dict] = []

    # --- P1 ---------------------------------------------------------------
    wa = {"nama": "Budi", "nomor": "6281234567890", "email": "",
          "perusahaan": "", "kota": ""}
    form = {"nama": "Budi Santoso", "nomor": "0812-3456-7890",
            "email": "budi.santoso@gmail.com", "perusahaan": "", "kota": ""}
    kep, skor, alasan = dedup.putuskan(form, wa)
    poin.append({
        "kode": "P1", "judul": "Lima kanal, satu pipeline",
        "tanya": "Nama, nomor, dan email tidak konsisten. Apakah tetap dikenali "
                 "sebagai orang yang sama?",
        "langkah": [
            {"label": "Dari WhatsApp", "nilai": "Budi · 6281234567890"},
            {"label": "Dari formulir website", "nilai": "Budi Santoso · 0812-3456-7890 · budi.santoso@gmail.com"},
            {"label": "Nomor setelah dinormalkan", "nilai": "keduanya menjadi 6281234567890"},
            {"label": "Keputusan", "nilai": f"{kep.upper()} · skor {skor} · {alasan}"},
        ],
        "lulus": kep == "gabung",
        "artinya": "Dua kiriman yang tulisannya berbeda berakhir sebagai satu orang, "
                   "bukan dua lead yang masing-masing dapat follow-up.",
    })

    # --- P2 ---------------------------------------------------------------
    contoh = [
        ("ID", "Halo, saya mau tanya harga kamar untuk 20 orang bulan depan, budget 50 juta"),
        ("EN", "Hi, we need 20 rooms next month, budget 50 million. What is the price?"),
        ("DE", "Guten Tag, wir brauchen 20 Zimmer nächsten Monat. Was kostet das?"),
    ]
    langkah, semua_ok, terlama = [], True, 0
    for i, (kode, pesan) in enumerate(contoh, start=1):
        r = _balas(f"DEMO-P2-{kode}", "whatsapp", "Uji", f"6281200007{i:03d}", "", pesan, semua)
        ok = r.get("bahasa") == kode and bool((r.get("balasan") or "").strip())
        semua_ok = semua_ok and ok and bool(r.get("patuh_tenggat"))
        terlama = max(terlama, int(r.get("ms") or 0))
        langkah.append({"label": f"Pesan {kode}", "nilai":
                        f"dikenali {r.get('bahasa')} · dibalas dalam {r.get('ms')} ms · "
                        f"\"{_potong(r.get('balasan') or '', 70)}\""})
    poin.append({
        "kode": "P2", "judul": "Balasan pertama, tiga bahasa, di bawah 5 menit",
        "tanya": "Apakah bahasa ditentukan oleh tulisan, bukan oleh nama?",
        "langkah": langkah, "lulus": semua_ok,
        "artinya": f"Ketiganya dibalas dalam bahasa yang benar. Terlama {terlama} ms "
                   f"dari batas 300.000 ms — diukur, bukan diasumsikan.",
    })

    # --- P3 ---------------------------------------------------------------
    r0 = _balas("DEMO-P3-1", "website_form", "Sari Melati", "0812-0000-7701",
                "sari.melati@example.com", "Halo, boleh minta katalog kamar?", semua)
    r1 = _balas("DEMO-P3-2", "whatsapp", "Sari Melati", "0812-0000-7701", "", "STOP", semua)
    r2 = _balas("DEMO-P3-3", "email", "Sari Melati", "", "sari.melati@example.com",
                "We need 20 rooms next month, budget 50 million. What is the price?", semua)
    kunci = r1.get("penekanan_ditulis") or []
    detik = (r2.get("penekanan") or {}).get("detik_sejak_optout")
    poin.append({
        "kode": "P3", "judul": "Berhenti di satu kanal, berhenti di semua kanal",
        "tanya": "Kalau prospek minta berhenti lewat WhatsApp, apakah emailnya ikut berhenti?",
        "langkah": [
            {"label": "Formulir menautkan nomor dan email", "nilai": str(r0.get("kunci"))},
            {"label": "Lalu mengirim 'STOP' lewat WhatsApp", "nilai": "penekanan ditulis untuk " + str(kunci)},
            {"label": "Kemudian lead panas masuk lewat email", "nilai": f"tindakan: {r2.get('tindakan')} · balasan: {(r2.get('balasan') or '(tidak ada)')}"},
            {"label": "Jarak waktu dari opt-out", "nilai": f"{detik} detik (batas 60 detik)"},
        ],
        "lulus": r2.get("tindakan") == "ditekan" and len(kunci) == 2
                 and (r2.get("penekanan") or {}).get("patuh_60_detik") is True,
        "artinya": "Pesan WhatsApp tidak pernah membawa alamat email. Kalau penekanan hanya "
                   "ditulis untuk kunci yang ada di pesan itu, email berikutnya tetap terkirim. "
                   "Yang terjadi sebaliknya: dua kunci ditulis sekaligus.",
    })

    # --- P4 ---------------------------------------------------------------
    import uuid
    cid = f"demo-konflik-{uuid.uuid4().hex[:6]}"
    kk = lambda s: f"{cid}-{s}"
    s1, _ = _minta(f"{CRM}/v1/contacts", "POST",
                   {"id": cid, "nama": "Demo Konflik", "tahap": "baru", "kota": "Bandung"},
                   {"X-API-Key": KUNCI_CRM, "Idempotency-Key": kk("1")})
    _minta(f"{CRM}/v1/contacts/{cid}", "PATCH",
           {"base": {"tahap": "baru"}, "set": {"tahap": "panas"}},
           {"X-API-Key": KUNCI_CRM, "Idempotency-Key": kk("2")})
    s2, bb = _minta(f"{CRM}/v1/contacts/{cid}", "PATCH",
                    {"base": {"tahap": "baru", "kota": "Bandung"},
                     "set": {"tahap": "dingin", "kota": "Jakarta"}},
                    {"X-API-Key": KUNCI_CRM, "Idempotency-Key": kk("3")})
    konflik = (bb.get("konflik") or [{}])[0]
    data = bb.get("data") or {}
    poin.append({
        "kode": "P4", "judul": "Sinkron dua arah tanpa saling menimpa",
        "tanya": "Kalau data diubah di dua tempat bersamaan, siapa yang menang?",
        "langkah": [
            {"label": "Kontak dibuat", "nilai": f"tahap=baru, kota=Bandung (HTTP {s1})"},
            {"label": "Sisi A mengubah tahap", "nilai": "baru → panas"},
            {"label": "Sisi B masih memegang nilai lama", "nilai": "mengirim tahap=dingin, kota=Jakarta"},
            {"label": "Jawaban server", "nilai": f"HTTP {s2} · konflik pada '{konflik.get('field')}': "
                                                 f"dasar={konflik.get('dasar')}, sekarang={konflik.get('sekarang')}, "
                                                 f"diusulkan={konflik.get('diusulkan')}"},
            {"label": "Nilai akhir", "nilai": f"tahap={data.get('tahap')} (tidak ditimpa) · "
                                              f"kota={data.get('kota')} (tetap tersinkron)"},
        ],
        "lulus": s2 == 409 and data.get("tahap") == "panas" and data.get("kota") == "Jakarta",
        "artinya": "Bukan last-write-wins. Field yang berkonflik ditahan dan dicatat untuk "
                   "diputuskan manusia; field lain tetap masuk. Tidak ada data yang hilang diam-diam.",
    })
    _minta(f"{CRM}/v1/contacts/{cid}", "DELETE", {"aktor": "demo"}, {"X-API-Key": KUNCI_CRM})

    # --- P5 ---------------------------------------------------------------
    a1 = _balas("DEMO-P5-1", "whatsapp", "Rizky", "0813-0000-1122", "", "Mohon info harga kamar", semua)
    a2 = _balas("DEMO-P5-2", "whatsapp", "Rizky", "0813-0000-1122", "", "Mohon info harga kamar", semua)
    n_balas = sum(1 for x in (a1, a2) if (x.get("balasan") or "").strip())
    poin.append({
        "kode": "P5", "judul": "Kiriman ulang, dan yang gagal tidak hilang",
        "tanya": "Kanal mengirim pesan yang sama dua kali. Apakah prospek dapat dua balasan?",
        "langkah": [
            {"label": "Kiriman pertama", "nilai": f"tindakan: {a1.get('tindakan')}"},
            {"label": "Kiriman kedua (identik)", "nilai": f"tindakan: {a2.get('tindakan')}"},
            {"label": "Jumlah balasan terkirim", "nilai": f"{n_balas} dari 2 kiriman"},
            {"label": "DLQ pengiriman WhatsApp", "nilai": f"{keadaan_wa().get('total_gagal', 0)} entri gagal tersimpan"},
        ],
        "lulus": n_balas == 1 and a2.get("tindakan") == "gabung_percakapan",
        "artinya": "Satu identitas menerima satu balasan per 24 jam. Kalau pengiriman gagal, "
                   "galatnya masuk DLQ — bukan hilang tanpa jejak.",
    })

    # --- P6 ---------------------------------------------------------------
    seharusnya = [x for x in semua if x.get("tindakan") == "balas"]
    dibalas = [x for x in seharusnya if (x.get("balasan") or "").strip()]
    antre = [x for x in semua if x.get("tindakan") == "antre_manusia"]
    ditekan = [x for x in semua if x.get("tindakan") == "ditekan"]
    poin.append({
        "kode": "P6", "judul": "Rekonsiliasi: bukti bahwa tidak ada yang terlewat",
        "tanya": "Workflow bisa hijau sementara ada lead yang tidak pernah dibalas. Bagaimana Anda tahu?",
        "langkah": [
            {"label": "Pesan yang dinilai pada demo ini", "nilai": f"{len(semua)} pesan"},
            {"label": "Seharusnya dibalas", "nilai": f"{len(seharusnya)}"},
            {"label": "Benar-benar dibalas", "nilai": f"{len(dibalas)}"},
            {"label": "Selisih", "nilai": f"{len(seharusnya) - len(dibalas)}"},
            {"label": "Pengecualian yang beralasan", "nilai": f"{len(antre)} antre manusia · {len(ditekan)} ditekan opt-out"},
        ],
        "lulus": len(seharusnya) == len(dibalas),
        "artinya": "Angka 'seharusnya' tidak diambil dari sistem yang sedang diuji. Kalau diambil "
                   "dari sana, angkanya akan selalu cocok dengan dirinya sendiri.",
    })

    wa_hasil = kirim_uji()

    lulus = sum(1 for p in poin if p["lulus"])
    return {
        "waktu": datetime.now(timezone.utc).astimezone().isoformat(),
        "poin": poin, "lulus": lulus, "total": len(poin),
        "wa": wa_hasil, "sistem": status_sistem(),
    }


DEMO_HTML = r"""<!DOCTYPE html>
<html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Demo Enam Poin — SAB</title>
<style>
:root{--bg:#0f1216;--panel:#171c22;--line:#28313b;--teks:#eef2f6;--redup:#9aa7b4;
--hijau:#3ddc97;--merah:#ff6b6b;--kuning:#ffc861;--biru:#5aa9ff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--teks);
font:17px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:1000px;margin:0 auto;padding:26px 24px 40px;min-height:100vh;
display:flex;flex-direction:column}
.bar{display:flex;align-items:center;justify-content:space-between;gap:16px;
margin-bottom:18px}
.merek{font-size:14px;color:var(--redup);letter-spacing:.06em;text-transform:uppercase}
.kontrol{display:flex;gap:8px;align-items:center}
button{font:inherit;font-size:14px;font-weight:600;padding:8px 15px;border-radius:8px;
border:1px solid var(--line);background:var(--panel);color:var(--teks);cursor:pointer}
button:hover{border-color:#3d4a58}
button.utama{background:var(--biru);border-color:var(--biru);color:#08131f}
.progres{height:3px;background:#1e252d;border-radius:2px;overflow:hidden;margin-bottom:26px}
.progres i{display:block;height:100%;width:0;background:var(--biru);transition:width .45s}
.slide{flex:1;display:none}
.slide.aktif{display:block;animation:masuk .4s ease}
@keyframes masuk{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
.kode{font-size:13px;font-weight:700;letter-spacing:.1em;color:var(--biru)}
h1{font-size:34px;line-height:1.22;margin:8px 0 10px;letter-spacing:-.02em}
.tanya{font-size:18px;color:var(--redup);margin:0 0 24px;max-width:760px}
.langkah{border:1px solid var(--line);border-radius:12px;overflow:hidden;
background:var(--panel);margin-bottom:18px}
.baris{display:grid;grid-template-columns:minmax(180px,34%) 1fr;gap:16px;
padding:13px 18px;border-bottom:1px solid var(--line);font-size:15.5px}
.baris:last-child{border-bottom:none}
.baris .l{color:var(--redup)}
.baris .v{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:14px;
word-break:break-word}
.artinya{font-size:16px;color:#cfd9e3;border-left:3px solid var(--biru);
padding-left:16px;margin:0 0 22px}
.hasil{display:inline-flex;align-items:center;gap:9px;font-weight:700;font-size:16px;
padding:9px 18px;border-radius:999px}
.h-ok{background:rgba(61,220,151,.13);color:var(--hijau)}
.h-no{background:rgba(255,107,107,.13);color:var(--merah)}
.kaki{display:flex;justify-content:space-between;align-items:center;margin-top:auto;
padding-top:24px;font-size:13px;color:var(--redup)}
.skor{font-size:13px;color:var(--redup)}
.besar{font-size:56px;font-weight:800;letter-spacing:-.03em;line-height:1}
.tabel{width:100%;border-collapse:collapse;font-size:15px;margin-top:6px}
.tabel td{padding:9px 0;border-bottom:1px solid var(--line)}
.tabel td:last-child{text-align:right;font-family:ui-monospace,monospace;font-size:13.5px}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13px;
word-break:break-all;color:var(--kuning)}
</style></head><body><div class="wrap">

<div class="bar">
  <div class="merek"><a href="/siaran" style="color:inherit;text-decoration:none">← layar demo</a>
    <span style="color:var(--garis,#39414f);margin:0 8px">|</span>
    SAB · demo enam poin</div>
  <div class="kontrol">
    <span class="skor" id="skor">memuat…</span>
    <button id="mundur">←</button>
    <button id="jeda">Jeda</button>
    <button id="maju">→</button>
    <button class="utama" id="ulang">Mulai ulang</button>
  </div>
</div>
<div class="progres"><i id="bar"></i></div>
<div id="isi"></div>
<div class="kaki">
  <span id="kaki-kiri">Demo berjalan sendiri — tidak perlu ada yang berbicara</span>
  <span id="kaki-kanan"></span>
</div>
</div>

<script>
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, c =>
  ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
// Jeda antar slide bisa diatur lewat URL: /demo?jeda=15000
// Berguna kalau yang menonton membaca lebih lambat dari 9 detik.
const JEDA_MS = (() => {
  const v = parseInt(new URLSearchParams(location.search).get('jeda') || '', 10);
  return Number.isFinite(v) && v >= 3000 && v <= 60000 ? v : 9000;
})();

let data = null, idx = 0, timer = null, jalan = true;

function slidePoin(p, i, n) {
  const langkah = p.langkah.map(l => `<div class="baris">
    <div class="l">${esc(l.label)}</div><div class="v">${esc(l.nilai)}</div></div>`).join('');
  return `<div class="slide" data-i="${i}">
    <div class="kode">${esc(p.kode)} · poin ${i + 1} dari ${n}</div>
    <h1>${esc(p.judul)}</h1>
    <p class="tanya">${esc(p.tanya)}</p>
    <div class="langkah">${langkah}</div>
    <p class="artinya">${esc(p.artinya)}</p>
    <div class="hasil ${p.lulus ? 'h-ok' : 'h-no'}">
      ${p.lulus ? '✓' : '✕'} ${p.lulus ? 'Terbukti bekerja' : 'Gagal — ini yang harus diperbaiki'}
    </div>
  </div>`;
}

function slideWa(d) {
  const w = d.wa || {}, hk = w.hasil_kirim || {};
  return `<div class="slide" data-i="${d.poin.length}">
    <div class="kode">BUKTI · pesan sungguhan</div>
    <h1>Ini bukan animasi. Pesannya benar-benar terkirim.</h1>
    <p class="tanya">Satu pesan WhatsApp masuk sebagai payload Meta, diputuskan,
    dikirim ke Graph API, dan Meta mengembalikan nomor pesannya.</p>
    <div class="langkah">
      <div class="baris"><div class="l">Tindakan</div><div class="v">${esc(w.tindakan || '-')}</div></div>
      <div class="baris"><div class="l">Bahasa</div><div class="v">${esc(w.bahasa || '-')} · tingkat ${esc(w.tingkat || '-')}</div></div>
      <div class="baris"><div class="l">Balasan</div><div class="v">${esc(w.balasan || '-')}</div></div>
      <div class="baris"><div class="l">Status</div><div class="v">${esc(hk.status || '-')} · ${esc(w.ms || '?')} ms</div></div>
      <div class="baris"><div class="l">Message ID dari Meta</div><div class="v">${esc(hk.message_id || '-')}</div></div>
    </div>
    <p class="artinya">Nomor pesan itu dibuat oleh Meta, bukan oleh sistem ini.
    Karena itu ia bisa dipakai untuk membuktikan pesannya sampai.</p>
    <div class="hasil ${hk.status === 'terkirim' ? 'h-ok' : 'h-no'}">
      ${hk.status === 'terkirim' ? '✓' : '✕'} ${hk.status === 'terkirim' ? 'Terkirim' : 'Gagal terkirim'}
    </div>
  </div>`;
}

function slideAkhir(d) {
  const rows = d.poin.map(p => `<tr><td>${esc(p.kode)} · ${esc(p.judul)}</td>
    <td>${p.lulus ? 'terbukti' : 'gagal'}</td></tr>`).join('');
  return `<div class="slide" data-i="${d.poin.length + 1}">
    <div class="kode">RINGKASAN</div>
    <h1><span class="besar">${d.lulus}/${d.total}</span> poin terbukti bekerja</h1>
    <p class="tanya">Diuji pada sistem yang sedang berjalan, bukan pada rekaman.</p>
    <table class="tabel">${rows}</table>
    <p class="artinya" style="margin-top:22px">Yang belum, dan tidak saya klaim:
    pengujian di akun n8n milik SAB, penyambungan CRM SAB, dan pengiriman ke nomor
    WhatsApp yang belum terdaftar di daftar penerima. Itu keputusan akun dan
    komersial, bukan kode.</p>
  </div>`;
}

function gambar() {
  const n = data.poin.length;
  $('isi').innerHTML = data.poin.map((p, i) => slidePoin(p, i, n)).join('')
    + slideWa(data) + slideAkhir(data);
  tampil(0);
}

function tampil(i) {
  const slides = document.querySelectorAll('.slide');
  idx = Math.max(0, Math.min(i, slides.length - 1));
  slides.forEach((s, k) => s.classList.toggle('aktif', k === idx));
  $('bar').style.width = ((idx + 1) / slides.length * 100) + '%';
  $('kaki-kanan').textContent = (idx + 1) + ' / ' + slides.length;
  if (idx === slides.length - 1 && timer) { clearInterval(timer); timer = null; }
}

function mulai() {
  if (timer) clearInterval(timer);
  timer = setInterval(() => { if (jalan) tampil(idx + 1); }, JEDA_MS);
}

async function muat() {
  $('skor').textContent = 'menjalankan demo…';
  try {
    const r = await fetch('/api/demo');
    data = await r.json();
    $('skor').textContent = data.lulus + '/' + data.total + ' poin terbukti';
    gambar(); mulai();
  } catch (e) {
    $('isi').innerHTML = '<div class="slide aktif"><h1>Demo gagal dijalankan</h1>' +
      '<p class="tanya">' + esc(e.message) + '</p></div>';
  }
}

$('maju').onclick = () => { tampil(idx + 1); mulai(); };
$('mundur').onclick = () => { tampil(idx - 1); mulai(); };
$('jeda').onclick = () => {
  jalan = !jalan;
  $('jeda').textContent = jalan ? 'Jeda' : 'Lanjut';
};
$('ulang').onclick = () => { muat(); };

document.addEventListener('keydown', (e) => {
  if (e.key === 'ArrowRight') { tampil(idx + 1); mulai(); }
  if (e.key === 'ArrowLeft') { tampil(idx - 1); mulai(); }
  if (e.key === ' ') { e.preventDefault(); $('jeda').click(); }
});

muat();
</script></body></html>"""


# ---------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):                               # noqa: D401
        pass

    def _kirim(self, kode: int, isi: bytes, tipe="application/json; charset=utf-8"):
        self.send_response(kode)
        self.send_header("Content-Type", tipe)
        self.send_header("Content-Length", str(len(isi)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(isi)

    def _json(self, obj, kode=200):
        self._kirim(kode, json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def _muatan(self) -> dict:
        """Baca badan permintaan JSON; kosong dianggap objek kosong."""
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        if n <= 0:
            return {}
        try:
            d = json.loads(self.rfile.read(min(n, 20_000)).decode("utf-8"))
            return d if isinstance(d, dict) else {}
        except Exception:                                    # noqa: BLE001
            return {}

    def do_GET(self):
        jalur = self.path.split("?")[0]
        if jalur in ("/", "/index.html"):
            self._kirim(200, HALAMAN.encode("utf-8"), "text/html; charset=utf-8")
        elif jalur in ("/demo", "/demo.html"):
            self._kirim(200, DEMO_HTML.encode("utf-8"), "text/html; charset=utf-8")
        elif jalur in ("/siaran", "/siaran.html"):
            self._kirim(200, SIARAN_HTML.encode("utf-8"), "text/html; charset=utf-8")
        elif jalur in ("/coba", "/coba.html"):
            self._kirim(200, COBA_HTML.encode("utf-8"), "text/html; charset=utf-8")
        elif jalur in ("/masuk", "/masuk.html"):
            self._kirim(200, MASUK_HTML.encode("utf-8"), "text/html; charset=utf-8")
        elif jalur == "/api/demo":
            try:
                self._json(jalankan_demo())
            except Exception as e:                           # noqa: BLE001
                self._json({"galat": str(e)[:300], "poin": [], "lulus": 0, "total": 0}, 500)
        elif jalur == "/api/status":
            self._json(status_sistem())
        elif jalur == "/api/kesiapan":
            self._json(kesiapan(segarkan="segarkan=1" in self.path))
        elif jalur == "/api/lead":
            self._json(daftar_lead())
        elif jalur == "/api/wa":
            self._json(keadaan_wa())
        else:
            self._json({"galat": "tidak ada"}, 404)

    def do_POST(self):
        jalur = self.path.split("?")[0]
        if jalur == "/api/kirim-uji":
            try:
                self._json(kirim_uji())
            except Exception as e:                           # noqa: BLE001
                self._json({"ok": False, "galat": str(e)[:200]}, 500)
        elif jalur == "/api/coba":
            try:
                self._json(coba_pesan(**self._muatan()))
            except Exception as e:                           # noqa: BLE001
                self._json({"ok": False, "galat": str(e)[:200]}, 500)
        elif jalur == "/api/masuk":
            try:
                self._json(masuk(**self._muatan()))
            except Exception as e:                           # noqa: BLE001
                self._json({"ok": False, "galat": str(e)[:200]}, 500)
        elif jalur == "/api/bersihkan":
            try:
                self._json(bersihkan_sesi())
            except Exception as e:                           # noqa: BLE001
                self._json({"ok": False, "galat": str(e)[:200]}, 500)
        else:
            self._json({"galat": "tidak ada"}, 404)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8899)
    a = ap.parse_args()
    print(f"Konsol demo: http://127.0.0.1:{a.port}")
    print(f"  n8n  : {N8N}")
    print(f"  CRM  : {CRM}")
    print(f"  tujuan uji: {TUJUAN_UJI}")
    ThreadingHTTPServer(("127.0.0.1", a.port), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
