"""Enam kanal, satu pipeline — diuji, bukan diklaim.

Yang dibuktikan di sini: lima kanal yang bentuknya tidak mirip sama sekali bisa
masuk ke satu tabel lead, dan dedup lintas kanal tetap bekerja di atasnya.
Termasuk dua hal yang paling mudah salah:

  - orang yang sama datang dari WhatsApp lalu dari form website (K01 + K06)
  - dua orang berbeda memakai satu email kantor (K04 Maria, K07 Joko) dan
    TIDAK boleh digabung

Jalankan: python uji_kanal.py
Keluar dengan kode 1 kalau ada satu saja yang gagal.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

AKAR = Path(__file__).resolve().parent
sys.path.insert(0, str(AKAR))
sys.path.insert(0, str(AKAR.parent / "ujian"))

import mesin          # noqa: E402
import normalkan      # noqa: E402

lulus = 0
gagal: list[str] = []


def cek(nama: str, syarat: bool, pesan: str = "") -> None:
    global lulus
    if syarat:
        lulus += 1
        print(f"  ok    {nama}")
    else:
        gagal.append(f"{nama}: {pesan}")
        print(f"  GAGAL {nama} — {pesan}")


def idempoten(baris: list[dict]) -> list[dict]:
    """Buang kiriman ulang berdasarkan id_kanal.

    Ini yang dijanjikan poin 5, dan di sini kuncinya bukan buatan: MessageSid
    dari Twilio, lead_id dari Google, message-id dari email — semuanya berasal
    dari kanalnya sendiri.
    """
    terlihat, keluar = set(), []
    for b in baris:
        k = b["id_kanal"]
        if k and k in terlihat:
            continue
        terlihat.add(k)
        keluar.append(b)
    return keluar


def utama() -> int:
    baris = normalkan.semua()

    print("== 1. Normalisasi ==")
    cek("tujuh baris masuk", len(baris) == 7, f"dapat {len(baris)}")
    cek("enam kanal berbeda", len({b['channel'] for b in baris}) == 6,
        f"dapat {sorted({b['channel'] for b in baris})}")
    cek("setiap baris punya kunci idempoten", all(b["id_kanal"] for b in baris),
        "ada yang kosong")
    cek("kunci idempoten unik", len({b['id_kanal'] for b in baris}) == len(baris),
        "ada yang kembar")
    cek("setiap baris punya bentuk yang sama",
        all(set(b) >= {"row_id", "channel", "name", "phone", "email",
                       "message", "id_kanal", "received_at"} for b in baris),
        "ada yang kurang field")
    cek("nomor dinormalkan ke bentuk yang sama",
        {b["_telp"] for b in baris if b["name"] == "Budi Santoso"} == {"6281200001101"},
        f"dapat {[b['_telp'] for b in baris if b['name'] == 'Budi Santoso']}")

    print("\n== 2. Idempotensi pada kunci kanal ==")
    ulang = baris + [dict(b) for b in baris]          # semua dikirim dua kali
    setelah = idempoten(ulang)
    cek("14 kiriman (7 x 2) menyusut jadi 7", len(setelah) == 7, f"dapat {len(setelah)}")

    print("\n== 3. Dedup lintas kanal ==")
    identitas, antre, stat, mungkin = mesin.kelompokkan(baris)
    cek("7 baris -> 5 identitas", len(identitas) == 5, f"dapat {len(identitas)}")
    cek("2 digabung otomatis", stat["digabung"] == 2, f"dapat {stat['digabung']}")

    per_id = {i["id"]: i for i in identitas}
    peta = {b["row_id"]: None for b in baris}
    for i in identitas:
        for rid in i["baris"]:
            peta[rid] = i["id"]

    cek("Budi dari WhatsApp dan form website jadi satu",
        peta["K01"] == peta["K06"] != None, f"{peta['K01']} vs {peta['K06']}")
    cek("Siti dari Meta Ads dan email jadi satu",
        peta["K02"] == peta["K05"] != None, f"{peta['K02']} vs {peta['K05']}")
    cek("Budi dan Siti bukan orang yang sama", peta["K01"] != peta["K02"],
        "dua orang berbeda tergabung")
    cek("Klaus dari Google Ads berdiri sendiri",
        per_id[peta["K03"]]["kanal"] == ["google_ads_form"],
        f"dapat {per_id[peta['K03']]['kanal']}")
    cek("Maria dari LinkedIn berdiri sendiri",
        per_id[peta["K04"]]["kanal"] == ["linkedin_form"],
        f"dapat {per_id[peta['K04']]['kanal']}")

    print("\n== 4. Jebakan email kantor dipakai bersama ==")
    cek("Maria dan Joko TIDAK digabung", peta["K04"] != peta["K07"],
        "dua orang berbeda tergabung lewat email kantor")
    cek("pasangan itu masuk antrean manusia", len(antre) == 1, f"dapat {len(antre)}")
    if antre:
        pasangan = {antre[0]["nama_a"], antre[0]["nama_b"]}
        cek("antrean berisi Maria dan Joko",
            pasangan == {"Maria Tan", "Joko Susilo"}, f"dapat {pasangan}")
        cek("antrean menyebut sebabnya",
            "dipakai bersama" in antre[0].get("jenis", "") or
            "dipakai bersama" in str(antre[0]),
            f"dapat {antre[0]}")

    print("\n== 5. Tidak ada yang hilang ==")
    semua_baris = sorted(r for i in identitas for r in i["baris"])
    cek("ketujuh baris terwakili di identitas",
        semua_baris == sorted(b["row_id"] for b in baris), f"dapat {semua_baris}")

    # Ringkasan untuk halaman. Ditulis dari hasil uji, bukan diketik di halaman.
    ringkas = {
        "baris": len(baris),
        "kanal": len({b["channel"] for b in baris}),
        "identitas": len(identitas),
        "digabung": stat["digabung"],
        "antrean": len(antre),
        "lulus": lulus + len(gagal),
        "benar": lulus,
        "tabel": [{"row_id": b["row_id"], "kanal": b["channel"], "nama": b["name"],
                   "telp": b["_telp"], "surel": b["_surel"],
                   "id_kanal": b["id_kanal"][:28]} for b in baris],
    }
    (AKAR / "hasil_kanal.json").write_text(
        json.dumps(ringkas, ensure_ascii=False, indent=1), encoding="utf-8")

    print("\n" + "=" * 62)
    if gagal:
        print(f"GAGAL: {len(gagal)} dari {lulus + len(gagal)} uji")
        for g in gagal:
            print("  - " + g)
        return 1
    print(f"LULUS: {lulus}/{lulus} uji kanal")
    print("6 kanal -> 1 pipeline, 7 baris -> 5 identitas, 0 salah gabung.")
    return 0


if __name__ == "__main__":
    raise SystemExit(utama())
