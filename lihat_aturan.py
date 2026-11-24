"""Tulis `aturan.json` — nilai yang benar-benar berlaku sekarang.

Alasan berkas ini ada: pada 23 November Tico bertanya, dengan kalimatnya
sendiri, "berapa ambang gabung otomatisnya, dan skor itu dihitung dari komponen
apa saja, dengan bobot berapa?". Pertanyaan seperti itu tidak boleh dijawab
dengan prosa. Jawabannya harus angka yang bisa ia periksa, dan angka itu harus
diambil dari kode yang berjalan — bukan diketik ulang di dokumen, karena
dokumen akan menyimpang dari kode.

Karena itu berkas ini membaca dua sumber:
  * `dedup.py` — ambang dan bobot, langsung dari modul yang dipakai.
  * workflow n8n `sabbalas01` — daftar spam dan daftar sinyal, langsung dari
    node yang berjalan saat pesan masuk.

Kalau salah satu sumber berubah, jalankan ulang skrip ini dan `aturan.json`
ikut berubah. Tidak ada angka yang ditulis tangan.

Pakai:
    python lihat_aturan.py            # tulis aturan.json + tampilkan ringkas
    python lihat_aturan.py --periksa  # hanya bandingkan, keluar 1 kalau beda
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

SAB = Path(__file__).resolve().parent
AKAR = SAB.parent
DB = AKAR / ".n8n_home" / ".n8n" / "database.sqlite"
KELUAR = SAB / "aturan.json"


def dari_dedup() -> dict:
    import dedup

    return {
        "ambang_gabung_otomatis": dedup.AMBANG_GABUNG,
        "ambang_antrean_manusia": dedup.AMBANG_ANTREAN,
        "bobot": {"nama_depan": dedup.BOBOT_DEPAN, "nama_marga": dedup.BOBOT_MARGA},
        "aturan_sapaan": (
            "Sapaan bergender yang bertentangan (Pak vs Ibu, Mas vs Mbak, "
            "Herr vs Frau) berarti dua orang berbeda, bukan nama mirip. "
            "Sapaan netral (H., Dr., Kak) dibuang sebelum membandingkan."
        ),
        "sumber": "dedup.py",
    }


def dari_n8n() -> dict:
    if not DB.exists():
        return {"_galat": "basis data n8n tidak ada"}
    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=5)
    row = db.execute("select nodes from workflow_entity where id='sabbalas01'").fetchone()
    db.close()
    if not row:
        return {"_galat": "workflow sabbalas01 tidak ada"}
    nodes = json.loads(row[0])
    js = next((n["parameters"]["jsCode"] for n in nodes
               if n["name"] == "Putuskan Balasan"), "")

    def pola(teks: str) -> list[str]:
        r"""Ambil isi tiap /pola/ dengan memindai, bukan regex.

        Pola regex sendiri mengandung `/` yang di-escape (`bit\.ly\/\S+`), jadi
        regex pencari pola akan salah potong. Pemindaian sederhana lebih jujur.
        """
        hasil, mulai, i = [], None, 0
        while i < len(teks):
            if teks[i] == "/" and (i == 0 or teks[i - 1] != "\\"):
                if mulai is None:
                    mulai = i + 1
                else:
                    hasil.append(teks[mulai:i])
                    mulai = None
            i += 1
        return [h for h in hasil if h and not h.startswith("*")]

    def daftar(nama: str) -> list[str]:
        m = re.search(rf"const {nama} = \[(.*?)\n\];", js, re.S) or \
            re.search(rf"const {nama} = \[(.*?)\];", js, re.S)
        return pola(m.group(1)) if m else []

    sinyal = {}
    blok = re.search(r"const SINYAL = \{(.*?)\n\};", js, re.S)
    if blok:
        for nama, isi in re.findall(r"(\w+): \{(.*?)\n  \},", blok.group(1), re.S):
            per_bahasa = {}
            for bhs, isi_bhs in re.findall(r"(ID|EN|DE): \[(.*?)\]", isi, re.S):
                per_bahasa[bhs] = pola(isi_bhs)
            if per_bahasa:
                sinyal[nama] = per_bahasa

    return {
        "spam": daftar("SPAM"),
        "spam_tambahan": daftar("SPAM_TAMBAHAN"),
        "sinyal": sinyal,
        "urutan_pemeriksaan": [
            "1. spam → karantina",
            "2. keluhan → antrean manusia (didahulukan atas anggaran)",
            "3. opt-out → berhenti di semua kanal",
            "4. anggaran DAN tenggat → balas otomatis",
            "5. selain itu → antrean manusia",
        ],
        "sumber": "workflow n8n sabbalas01, node 'Putuskan Balasan'",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--periksa", action="store_true")
    a = ap.parse_args()

    sekarang = {"dedup": dari_dedup(), "kualifikasi": dari_n8n()}

    if a.periksa:
        try:
            lama = json.loads(KELUAR.read_text(encoding="utf-8"))
        except Exception:                                    # noqa: BLE001
            print("aturan.json belum ada")
            return 1
        beda = [k for k in sekarang if lama.get(k) != sekarang[k]]
        print("berbeda:", beda or "tidak ada")
        return 1 if beda else 0

    KELUAR.write_text(json.dumps(sekarang, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    d = sekarang["dedup"]
    print(f"ditulis: {KELUAR.name}")
    print(f"  ambang gabung otomatis : {d['ambang_gabung_otomatis']}")
    print(f"  ambang antrean manusia : {d['ambang_antrean_manusia']}")
    print(f"  bobot                  : depan {d['bobot']['nama_depan']} · "
          f"marga {d['bobot']['nama_marga']}")
    k = sekarang["kualifikasi"]
    print(f"  pola spam              : {len(k.get('spam', [])) + len(k.get('spam_tambahan', []))}")
    print(f"  kelompok sinyal        : {', '.join(k.get('sinyal', {})) or '-'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
