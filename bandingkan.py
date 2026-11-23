"""Bandingkan hasil dedup lama vs baru pada data uji yang sama.

Dipakai untuk menjawab pertanyaan SAB: apa yang berubah, dan kenapa satu per satu.
Jalankan: python bandingkan.py
"""
from __future__ import annotations

import importlib
import json
from pathlib import Path

AKAR = Path(__file__).parent


def kelompokkan(dedup, lead: list[dict]):
    """Salinan alur gabungkan() dari demo.py, tapi modulnya bisa dipilih."""
    identitas: list[dict] = []
    antrean: list[dict] = []
    indeks_nomor: dict[str, int] = {}
    indeks_email: dict[str, int] = {}
    indeks_blok: dict[str, set[int]] = {}

    def buat_baru(l: dict) -> int:
        # Semua field yang dibaca putuskan() harus ikut disimpan. Versi pertama
        # skrip ini hanya menyimpan nama dan kota, sehingga perbandingan
        # berikutnya memakai perusahaan/nomor kosong dan angkanya salah.
        identitas.append({"id": f"ID{len(identitas):03d}", "nama": l["nama"],
                          "nomor": l.get("nomor", ""), "email": l.get("email", ""),
                          "perusahaan": l.get("perusahaan", ""),
                          "kota": l["kota"], "_orang": {l["_orang"]}})
        i = len(identitas) - 1
        n, e = dedup.nomor(l.get("nomor", "")), dedup.email(l.get("email", ""))
        if n:
            indeks_nomor.setdefault(n, i)
        if e:
            indeks_email.setdefault(e, i)
        for k in dedup.kunci_blok(l):
            indeks_blok.setdefault(k, set()).add(i)
        return i

    for l in lead:
        n, e = dedup.nomor(l.get("nomor", "")), dedup.email(l.get("email", ""))
        ketemu = indeks_nomor.get(n) if n else None
        if ketemu is None and e:
            ketemu = indeks_email.get(e)

        if ketemu is None:
            kandidat: set[int] = set()
            for k in dedup.kunci_blok(l):
                kandidat |= indeks_blok.get(k, set())
            calon_gabung, skor_gabung = None, 0.0
            calon_antre, skor_antre, alasan = None, 0.0, ""
            for i in kandidat:
                kep, skor, als = dedup.putuskan(l, identitas[i])
                if kep == "gabung" and skor > skor_gabung:
                    calon_gabung, skor_gabung = i, skor
                elif kep == "antrean" and skor > skor_antre:
                    calon_antre, skor_antre, alasan = i, skor, als
            if calon_gabung is not None:
                ketemu = calon_gabung
            else:
                if calon_antre is not None:
                    antrean.append({
                        "lead": l["event_id"], "nama_lead": l["nama"],
                        "orang_lead": l["_orang"],
                        "calon": identitas[calon_antre]["id"],
                        "nama_calon": identitas[calon_antre]["nama"],
                        "orang_calon": next(iter(identitas[calon_antre]["_orang"])),
                        "skor": skor_antre, "alasan": alasan})
                buat_baru(l)
                continue
        identitas[ketemu]["_orang"].add(l["_orang"])
        if n:
            indeks_nomor.setdefault(n, ketemu)
        if e:
            indeks_email.setdefault(e, ketemu)

    return identitas, antrean


def main() -> None:
    lama = importlib.import_module("dedup_lama")
    baru = importlib.import_module("dedup")
    data = json.loads((AKAR / "data_uji.json").read_text(encoding="utf-8"))
    lead = data["lead"]

    id_lama, q_lama = kelompokkan(lama, lead)
    id_baru, q_baru = kelompokkan(baru, lead)

    print("=" * 70)
    print("PERBANDINGAN DEDUP — data uji yang sama, 200 lead")
    print("=" * 70)
    baris = [
        ("identitas", len(id_lama), len(id_baru)),
        ("digabung otomatis", len(lead) - len(id_lama), len(lead) - len(id_baru)),
        ("pasangan di antrean", len(q_lama), len(q_baru)),
        ("salah gabung", sum(1 for i in id_lama if len(i["_orang"]) > 1),
         sum(1 for i in id_baru if len(i["_orang"]) > 1)),
    ]
    print(f"\n{'ukuran':26s} {'lama':>8s} {'baru':>8s}")
    for nama, a, b in baris:
        tanda = "" if a == b else "   <-- berubah"
        print(f"{nama:26s} {a:>8d} {b:>8d}{tanda}")

    def kunci(q):
        return frozenset([q["nama_lead"], q["nama_calon"]])

    peta_lama = {kunci(q): q for q in q_lama}
    peta_baru = {kunci(q): q for q in q_baru}
    hilang = [peta_lama[k] for k in peta_lama if k not in peta_baru]
    muncul = [peta_baru[k] for k in peta_baru if k not in peta_lama]

    print(f"\n--- {len(hilang)} pasangan yang TIDAK LAGI masuk antrean ---")
    for q in hilang:
        sama = q["orang_lead"] == q["orang_calon"]
        jenis = ("ORANG SAMA (terpecah, aman)" if sama
                 else "ORANG BERBEDA (memang harusnya keluar)")
        print(f"  {q['nama_lead']!r} vs {q['nama_calon']!r}")
        print(f"     skor lama {q['skor']:.3f} | {jenis}")
        print(f"     alasan lama: {q['alasan']}")

    if muncul:
        print(f"\n--- {len(muncul)} pasangan BARU masuk antrean ---")
        for q in muncul:
            print(f"  {q['nama_lead']!r} vs {q['nama_calon']!r} skor {q['skor']:.3f}"
                  f" | {q['alasan']}")

    # jawaban untuk pertanyaan SAB: 30 duplikat itu ke mana?
    print("\n" + "=" * 70)
    print("REKONSILIASI 30 DUPLIKAT (pertanyaan SAB poin 4)")
    print("=" * 70)
    asal: dict[str, list[int]] = {}
    for i, ident in enumerate(id_baru):
        for o in ident["_orang"]:
            asal.setdefault(o, []).append(i)
    terpecah = {o: v for o, v in asal.items() if len(v) > 1}
    digabung = len(lead) - len(id_baru)
    print(f"  lead mentah                 : {len(lead)}")
    print(f"  orang unik sebenarnya       : {len(data['orang'])}")
    print(f"  duplikat yang ditanam       : {len(lead) - len(data['orang'])}")
    print(f"  digabung otomatis (nomor/email): {digabung}")
    print(f"  orang terpecah jadi 2 id    : {len(terpecah)}")
    print(f"  identitas akhir             : {len(id_baru)}")
    print(f"  cek: {len(data['orang'])} orang + {len(terpecah)} kelebihan "
          f"= {len(data['orang']) + len(terpecah)}")
    print(f"  pasangan masih di antrean   : {len(q_baru)}")
    print("\n  Artinya: dari 30 duplikat, "
          f"{digabung} berhasil digabung otomatis, "
          f"{len(terpecah)} terpecah (aman, tidak salah gabung),")
    print("  dan antrean berisi pasangan yang BELUM diputuskan -- bukan duplikat")
    print("  yang sudah dihitung. Angka 173 adalah identitas SEMENTARA.")


if __name__ == "__main__":
    main()
