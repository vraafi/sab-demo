"""Uji kesamaan: mesin.py (Python) vs workflow n8n.

Ini jawaban untuk pertanyaan Tico nomor 7 — "sistemnya dibangun di n8n atau
sebagai layanan Python?". Jawabannya: dibangun di n8n. Python hanya alat ukur
yang dipakai untuk memeriksa hasil n8n. Karena itu keduanya harus menghasilkan
angka yang sama pada data yang sama, dan skrip ini membuktikannya — bukan
menyatakan.

Jalankan: python uji_kesamaan.py
Keluar dengan kode 1 kalau ada satu saja yang berbeda.
"""
from __future__ import annotations

import json
from pathlib import Path

AKAR = Path(__file__).resolve().parent


def main() -> int:
    py = json.loads((AKAR / "hasil_ujian.json").read_text(encoding="utf-8"))
    n8 = json.loads((AKAR / "hasil_ujian_n8n.json").read_text(encoding="utf-8"))

    beda: list[str] = []
    dihitung = 0

    def sama(nama: str, a, b) -> None:
        nonlocal dihitung
        dihitung += 1
        if a != b:
            beda.append(f"{nama}: python={a!r} n8n={b!r}")

    # Poin 1 — dedup
    for k in ("baris_masuk", "identitas", "digabung",
              "kontak_dipakai_bersama", "kemungkinan_duplikat_nama"):
        sama(f"poin1.{k}", py["poin_1_dedup"].get(k), n8["poin_1_dedup"].get(k))
    sama("poin1.kontak_bersama", py["poin_1_dedup"]["kontak_bersama"],
         n8["poin_1_dedup"]["kontak_bersama"])
    sama("poin1.kemungkinan_duplikat",
         py["poin_1_dedup"]["kemungkinan_duplikat"],
         n8["poin_1_dedup"]["kemungkinan_duplikat"])

    # Poin 2 — bahasa
    sama("poin2.sebaran", py["poin_2_bahasa"]["sebaran"],
         n8["poin_2_bahasa"]["sebaran"])

    # Poin 3 — opt-out, spam, lintas kanal
    sama("poin3.opt_out",
         [x["identitas"] for x in py["poin_3_optout"]["opt_out"]],
         n8["poin_3_optout"]["opt_out"])
    sama("poin3.spam", [x["identitas"] for x in py["spam"]],
         n8["poin_3_optout"]["spam"])
    sama("poin3.lintas_kanal", py["poin_3_optout"]["lintas_kanal"],
         n8["poin_3_optout"]["lintas_kanal"])

    # Poin 5 — kirim, DLQ, alarm
    p5, n5 = py["poin_5_kirim"], n8["poin_5_kirim"]
    sama("poin5.terkirim", p5["terkirim"], n5["terkirim"])
    sama("poin5.dlq_awal", p5["dlq_awal"], n5["dlq_awal"])
    sama("poin5.dipulihkan", p5["dipulihkan"], n5["dipulihkan"])
    sama("poin5.dlq_akhir", p5["dlq_setelah_putar_ulang"],
         n5["dlq_setelah_putar_ulang"])
    sama("poin5.alarm_saat_kirim", p5["alarm_kedalaman_dlq_saat_kirim"],
         n5["alarm_saat_kirim"])
    sama("poin5.alarm_akhir", p5["alarm_kedalaman_dlq_setelah_putar_ulang"],
         n5["alarm_setelah_putar_ulang"])
    sama("poin5.dlq_isi", [d["identitas"] for d in p5["dlq"]],
         [d["identitas"] for d in n5["dlq"]])
    # Percobaan ulang: jumlah item yang dicoba lebih dari sekali dan jumlah
    # percobaan seluruhnya. Kalau n8n tidak benar-benar mengulang, angka ini
    # akan jatuh ke 33 dan uji ini gagal.
    sama("poin5.item_dicoba_ulang", p5["item_dicoba_ulang"],
         n5["item_dicoba_ulang"])
    sama("poin5.total_percobaan", p5["total_percobaan"], n5["total_percobaan"])

    # Poin 6 — rekonsiliasi
    p6, n6 = py["poin_6_rekonsiliasi"], n8["poin_6_rekonsiliasi"]
    for k in ("seharusnya_dibalas", "benar_benar_dibalas", "selisih",
              "pengecualian"):
        sama(f"poin6.{k}", p6[k], n6[k])

    print("=" * 70)
    print("UJI KESAMAAN: mesin.py (Python) vs workflow n8n")
    print("=" * 70)
    if beda:
        print(f"{len(beda)} PERBEDAAN:")
        for b in beda:
            print("  -", b)
        return 1
    print(f"Tidak ada perbedaan pada {dihitung} angka yang dibandingkan.")
    print("Artinya: logika yang diuji di Python memang yang berjalan di n8n.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
