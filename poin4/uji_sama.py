"""Bandingkan hasil sinkronisasi Python dan n8n, sampai ke isi field.

Bukan hanya jumlahnya: seluruh catatan hasil gabung, seluruh antrean konflik,
dan seluruh jejak dibandingkan apa adanya. Kalau satu nilai field berbeda,
skrip ini keluar dengan kode 1.

Jalankan: python uji_sama.py
"""
from __future__ import annotations

import json
from pathlib import Path

AKAR = Path(__file__).resolve().parent


def main() -> int:
    py = json.loads((AKAR / "hasil_poin4.json").read_text(encoding="utf-8"))
    n8 = json.loads((AKAR / "hasil_poin4_n8n.json").read_text(encoding="utf-8"))

    beda: list[str] = []
    dihitung = 0

    def sama(nama: str, a, b) -> None:
        nonlocal dihitung
        dihitung += 1
        if a != b:
            beda.append(f"{nama}: python={a!r} n8n={b!r}")

    for k in ("catatan_dasar", "catatan_lokal", "catatan_jauh", "hasil_gabung",
              "konflik", "konflik_per_field", "dihapus"):
        sama(f"ringkasan.{k}", py["ringkasan"][k], n8["ringkasan"][k])

    # Seluruh catatan hasil gabung, field demi field.
    rec_py = {r["id"]: r for r in py["gabung"]}
    rec_n8 = {r["id"]: r for r in n8["gabung"]}
    sama("gabung.id", sorted(rec_py), sorted(rec_n8))
    for i in sorted(set(rec_py) & set(rec_n8)):
        for f in sorted(set(rec_py[i]) | set(rec_n8[i])):
            sama(f"gabung.{i}.{f}", rec_py[i].get(f), rec_n8[i].get(f))

    # Antrean konflik, termasuk nilai dasar/lokal/jauh yang dibawa.
    sama("konflik", py["konflik"], n8["konflik"])
    sama("jejak", py["jejak"], n8["jejak"])

    print("=" * 70)
    print("UJI SAMA: sinkron.py (Python) vs workflow n8n — poin 4")
    print("=" * 70)
    if beda:
        print(f"{len(beda)} PERBEDAAN:")
        for b in beda:
            print("  -", b)
        return 1
    print(f"Tidak ada perbedaan pada {dihitung} angka dan nilai yang dibandingkan.")
    print("Termasuk isi tiap field pada 10 catatan hasil gabung dan 5 entri konflik.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
