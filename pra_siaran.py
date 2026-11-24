"""Pemeriksaan lima menit sebelum berbagi layar.

Yang diperiksa bukan "apakah kode benar" — itu tugas uji lain. Yang diperiksa
adalah hal-hal yang membuat panggilan gagal padahal sistemnya sehat:

  * ada layanan yang belum menyala,
  * halaman yang akan dibagikan tidak bisa dibuka,
  * daftar kontak berisi sisa data uji sehingga layar terlihat berantakan,
  * kiriman WhatsApp yang gagal menumpuk tanpa ada yang tahu,
  * rekaman cadangan hilang.

Keluaran: SATU baris putusan, lalu daftar singkat apa yang harus dilakukan.

Pakai:
    python pra_siaran.py            # periksa saja
    python pra_siaran.py --buka     # periksa, lalu buka halaman siaran
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

SAB = Path(__file__).resolve().parent
AKAR = SAB.parent

N8N = "http://127.0.0.1:5678"
CRM = "http://127.0.0.1:8787"
DEMO = "http://127.0.0.1:8899"
TUNNEL = AKAR / "tmp" / "tunnel_url.txt"
DB = AKAR / ".n8n_home" / ".n8n" / "database.sqlite"
VIDEO = SAB / "DEMO_SAB.mp4"

HIJAU, MERAH, KUNING, MATI = "\033[92m", "\033[91m", "\033[93m", "\033[0m"


def minta(url: str, timeout: float = 6.0, kepala: dict | None = None):
    req = urllib.request.Request(url, headers=kepala or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(200_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read(4_000).decode("utf-8", "replace")
    except Exception:                                        # noqa: BLE001
        return 0, ""


def kunci_crm() -> str:
    for kandidat in (SAB / "poin4", SAB / "crm", SAB):
        for f in kandidat.glob("*.py"):
            try:
                teks = f.read_text(encoding="utf-8", errors="ignore")
            except Exception:                                # noqa: BLE001
                continue
            for baris in teks.splitlines():
                if "KUNCI_CRM" in baris and "=" in baris and "os." not in baris:
                    nilai = baris.split("=", 1)[1].strip().strip('"\'')
                    if 8 < len(nilai) < 80:
                        return nilai
    return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--buka", action="store_true", help="buka halaman siaran di browser")
    a = ap.parse_args()

    wajib: list[tuple[bool, str, str]] = []   # (lulus, nama, keterangan)
    saran: list[tuple[bool, str, str]] = []

    # --- tiga layanan yang harus hidup -----------------------------------
    s, _ = minta(f"{N8N}/healthz")
    wajib.append((s == 200, "n8n menyala", f"HTTP {s} · {N8N}"))

    s, _ = minta(f"{CRM}/health")
    wajib.append((s == 200, "CRM menyala", f"HTTP {s} · {CRM}"))

    s, isi = minta(f"{DEMO}/siaran")
    wajib.append((s == 200 and "Enam tombol" in isi,
                  "halaman siaran terbuka",
                  f"HTTP {s} · {DEMO}/siaran"))

    # --- data di layar tidak boleh terlihat seperti tempat uji -----------
    kunci = kunci_crm()
    s, isi = minta(f"{CRM}/v1/contacts", kepala={"X-API-Key": kunci} if kunci else {})
    bersih = 0
    kotor = 0
    if s == 200:
        try:
            for k in (json.loads(isi).get("data") or []):
                nama = (k.get("nama") or k.get("name") or "").strip()
                if k.get("dihapus") or not nama:
                    continue
                if nama.lower().startswith("uji "):
                    kotor += 1
                else:
                    bersih += 1
        except Exception:                                    # noqa: BLE001
            pass
    wajib.append((bersih >= 3, "ada kontak layak ditampilkan",
                  f"{bersih} kontak bersih · {kotor} sisa uji (disaring otomatis)"))

    # --- kiriman gagal tidak boleh menumpuk ------------------------------
    gagal = terkirim = -1
    ditolak_daftar = 0
    if DB.exists():
        try:
            db = sqlite3.connect(DB)
            row = db.execute("select staticData from workflow_entity "
                             "where id='sabwacloud01'").fetchone()
            db.close()
            g = json.loads(row[0]).get("global", {}) if row and row[0] else {}
            isi_gagal = g.get("gagal", [])
            gagal = len(isi_gagal)
            terkirim = len(g.get("terkirim", []))
            # Penolakan "nomor tidak ada di daftar penerima" (131030) memang
            # akan terjadi saat demo — Tico akan mencoba nomornya sendiri.
            # Itu bukan kerusakan, jadi jangan sampai menghalangi panggilan.
            for e in isi_gagal:
                if "131030" in str((e.get("galat") or {}).get("message") or ""):
                    ditolak_daftar += 1
        except Exception:                                    # noqa: BLE001
            pass
    gagal_lain = max(0, gagal - ditolak_daftar)
    wajib.append((gagal_lain == 0, "tidak ada kegagalan di luar daftar penerima",
                  f"{terkirim} terkirim · {gagal} gagal "
                  f"({ditolak_daftar} ditolak daftar penerima — wajar)"))

    # --- rekaman cadangan ------------------------------------------------
    ada_video = VIDEO.exists()
    ukuran = VIDEO.stat().st_size / 1024 / 1024 if ada_video else 0
    saran.append((ada_video, "rekaman cadangan tersedia",
                  f"{VIDEO.name} · {ukuran:.1f} MB" if ada_video
                  else "belum direkam — jalankan: python rekam_demo.py --jeda 14"))

    # --- tunnel: hanya perlu kalau ingin pesan dari ponsel sungguhan -----
    tun = ""
    try:
        tun = TUNNEL.read_text(encoding="utf-8").strip().splitlines()[0]
    except Exception:                                        # noqa: BLE001
        pass
    s_tun, _ = minta(f"{tun}/healthz", timeout=4) if tun else (0, "")
    saran.append((s_tun == 200, "tunnel hidup (untuk pesan dari ponsel asli)",
                  tun or "alamat tunnel belum ada"))

    # --- laporkan --------------------------------------------------------
    print()
    for lulus, nama, ket in wajib:
        tanda = f"{HIJAU}OK  {MATI}" if lulus else f"{MERAH}GAGAL{MATI}"
        print(f"  {tanda}  {nama:38} {ket}")
    print()
    for lulus, nama, ket in saran:
        tanda = f"{HIJAU}ada {MATI}" if lulus else f"{KUNING}tidak{MATI}"
        print(f"  {tanda}  {nama:38} {ket}")

    penghalang = [n for lulus, n, _ in wajib if not lulus]
    print()
    if penghalang:
        print(f"{MERAH}JANGAN BAGIKAN LAYAR DULU.{MATI} Yang harus dibereskan:")
        for n in penghalang:
            print(f"   - {n}")
        if any("menyala" in n or "terbuka" in n for n in penghalang):
            print(f"\n   Jalankan:  python {SAB.name}/demo_server.py")
            print("   (n8n dan CRM harus menyala lebih dulu)")
        return 1

    print(f"{HIJAU}SIAP.{MATI} Buka {DEMO}/siaran , tekan F11, lalu bagikan jendela itu.")
    print("   Urutan klik: 1 kirim · 2 coba sendiri · 3 daftar · 4 mesin · 5 apa yang belum · 6 enam poin")
    if a.buka:
        webbrowser.open(f"{DEMO}/siaran")
    return 0


if __name__ == "__main__":
    sys.exit(main())
