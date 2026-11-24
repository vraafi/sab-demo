"""Terapkan perubahan aturan ke workflow n8n dengan satu perintah.

Alasan berkas ini ada: Tico menulis bahwa di sesi Meet ia akan "minta satu
perubahan dikerjakan langsung". Kalau perubahan itu harus dikerjakan dengan
membongkar kode di depan orang, yang terlihat adalah orang yang sedang panik —
bukan orang yang menguasai sistemnya.

Karena itu perubahannya disiapkan lebih dulu, sebagai preset. Saat diminta, yang
dikerjakan adalah satu perintah, dan yang tampil di layar adalah selisih sebelum
dan sesudahnya.

Pakai:
    python ubah_aturan.py --lihat
    python ubah_aturan.py --preset longgar --dry-run
    python ubah_aturan.py --preset longgar --terapkan

Sesudah --terapkan, n8n harus dinyalakan ulang (2 menit). Skrip ini tidak
melakukannya sendiri: mematikan proses dari dalam proses adalah cara paling
mudah membuat demo mati tepat saat dipakai.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
import time
from pathlib import Path

SAB = Path(__file__).resolve().parent
AKAR = SAB.parent
DB = AKAR / ".n8n_home" / ".n8n" / "database.sqlite"
CADANGAN = SAB / "tmp"
WF = "sabbalas01"
NODE = "Putuskan Balasan"

# ---------------------------------------------------------------------------
# Preset. Setiap preset adalah selisih teks yang pasti ada, bukan pencarian
# samar: kalau teksnya tidak ditemukan, skrip berhenti dan tidak mengubah apa
# pun. Lebih baik gagal terang-terangan daripada mengubah separuh.
# ---------------------------------------------------------------------------
SYARAT_KETAT = r"""  if (tanda.indexOf('menyebut anggaran') >= 0 && tanda.indexOf('menyebut tenggat') >= 0) {"""
SYARAT_LONGGAR = r"""  if (tanda.length > 0) {"""

PRESET: dict[str, dict] = {
    "longgar": {
        "judul": "Balas semua yang menyebut salah satu sinyal (bukan harus anggaran + tenggat)",
        "ganti": [(SYARAT_KETAT, SYARAT_LONGGAR)],
        "akibat": "Mesin demo akan membalas jauh lebih banyak lead. Pada berkas 50 "
                  "lead Tico, angka balasan naik dari 3 mendekati 33 — karena "
                  "definisinya yang berubah, bukan mesinnya.",
    },
    "ketat": {
        "judul": "Kembalikan ke syarat ketat: anggaran DAN tenggat",
        "ganti": [(SYARAT_LONGGAR, SYARAT_KETAT)],
        "akibat": "Hanya prospek yang menyebut anggaran dan tenggat yang dibalas "
                  "otomatis; sisanya ke antrean manusia.",
    },
    "tanpa_keluhan": {
        "judul": "Keluhan tidak lagi dipaksa ke antrean manusia",
        "ganti": [(
            r"""  if (cari('keluhan', bhs, teks)) {
    return { tingkat: 'manusia', alasan: ['keluhan — perlu orang, bukan templat'] };""",
            r"""  if (false && cari('keluhan', bhs, teks)) {
    return { tingkat: 'manusia', alasan: ['keluhan — perlu orang, bukan templat'] };""",
        )],
        "akibat": "Keluhan akan diperlakukan seperti pertanyaan biasa. Saya tidak "
                  "menyarankan ini, tetapi ini yang paling sering diminta orang "
                  "yang ingin semua pesan dibalas.",
    },
}


def baca() -> tuple[sqlite3.Connection, str, str]:
    db = sqlite3.connect(DB)
    row = db.execute("select nodes, activeVersionId from workflow_entity where id=?",
                     (WF,)).fetchone()
    if not row:
        raise SystemExit(f"workflow {WF} tidak ada")
    return db, row[0], row[1]


def cari_js(nodes_teks: str) -> tuple[list, str]:
    nodes = json.loads(nodes_teks)
    for n in nodes:
        if n.get("name") == NODE:
            return nodes, n["parameters"]["jsCode"]
    raise SystemExit(f"node {NODE} tidak ada")


def lihat() -> int:
    db, nodes_teks, _ = baca()
    db.close()
    _, js = cari_js(nodes_teks)
    longgar = SYARAT_LONGGAR in js
    print(f"workflow : {WF}")
    print(f"node     : {NODE}")
    print(f"syarat   : {'LONGGAR (salah satu sinyal)' if longgar else 'KETAT (anggaran + tenggat)'}")
    print(f"keluhan  : {'TIDAK dipaksa ke manusia' if 'if (false && cari' in js else 'dipaksa ke antrean manusia'}")
    print(f"panjang  : {len(js)} huruf")
    print("\npreset yang tersedia:")
    for nama, p in PRESET.items():
        print(f"  {nama:15} {p['judul']}")
    return 0


def terapkan(nama: str, dry: bool) -> int:
    p = PRESET.get(nama)
    if not p:
        print(f"preset tidak ada: {nama}")
        return 1

    db, nodes_teks, versi = baca()
    nodes, js = cari_js(nodes_teks)

    baru = js
    for lama, ganti in p["ganti"]:
        if lama not in baru:
            print("BERHENTI: teks yang mau diganti tidak ditemukan.")
            print("  Yang dicari:", lama.splitlines()[0][:90])
            print("  Artinya workflow sudah berubah dari yang skrip ini kenal.")
            print("  Tidak ada yang diubah.")
            db.close()
            return 2
        baru = baru.replace(lama, ganti)

    print(f"preset   : {nama} — {p['judul']}")
    print(f"akibat   : {p['akibat']}")
    print(f"selisih  : {len(js)} → {len(baru)} huruf")

    if dry:
        print("\n(dry-run: tidak ada yang ditulis)")
        db.close()
        return 0

    CADANGAN.mkdir(exist_ok=True)
    cap = CADANGAN / f"cadangan_{WF}_{time.strftime('%H%M%S')}.json"
    cap.write_text(nodes_teks, encoding="utf-8")

    for n in nodes:
        if n.get("name") == NODE:
            n["parameters"]["jsCode"] = baru
    teks = json.dumps(nodes, ensure_ascii=False)
    db.execute("update workflow_entity set nodes=? where id=?", (teks, WF))
    db.execute("update workflow_history set nodes=? where workflowId=? and versionId=?",
               (teks, WF, versi))
    db.commit()
    db.close()

    print(f"\ntersimpan. Cadangan: {cap.name}")
    print("SEKARANG: matikan n8n lalu nyalakan lagi (2 menit).")
    print("  taskkill /PID <pid n8n> /F   lalu jalankan perintah n8n seperti biasa")
    print("  Setelah hidup, jalankan: python lihat_aturan.py --periksa")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lihat", action="store_true")
    ap.add_argument("--preset", choices=sorted(PRESET))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--terapkan", action="store_true")
    a = ap.parse_args()

    if a.lihat or not a.preset:
        return lihat()
    if not a.terapkan and not a.dry_run:
        print("Pilih --dry-run untuk melihat, atau --terapkan untuk menulis.")
        return 1
    return terapkan(a.preset, a.dry_run)


if __name__ == "__main__":
    sys.exit(main())
