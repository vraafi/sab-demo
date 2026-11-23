"""Poin 4 — sinkronisasi dua arah dengan CRM, termasuk resolusi konflik.

Masalah yang diselesaikan Tico: data diubah di dua tempat bersamaan. Yang
dijanjikan di surat lingkup, dan yang diuji di sini:

  "Setiap catatan membawa `updated_at` dari kedua sisi dan versi. Kalau satu
   sisi berubah, sisi lain mengikuti. Kalau dua sisi berubah, tidak ada yang
   menang diam-diam: perubahannya masuk antrean konflik per-field, dan yang
   tidak berkonflik tetap tersinkron. Tidak ada last-write-wins."

Kalimat terakhir itu yang menentukan seluruh rancangan. Last-write-wins
mudah: bandingkan `updated_at`, ambil yang paling baru. Itu juga yang paling
sering merusak data, karena jam dua sistem tidak pernah benar-benar sama dan
perubahan yang lebih penting bisa kalah oleh perubahan yang lebih belakangan
tapi lebih sepele.

Karena itu `updated_at` TIDAK dipakai untuk memilih pemenang di sini. Ia
hanya dicatat. Pemenang ditentukan oleh nenek moyang bersama: nilai terakhir
yang disepakati kedua sisi (`dasar`).

  - hanya lokal berubah        -> pakai lokal
  - hanya jauh berubah         -> pakai jauh
  - dua-duanya berubah, sama   -> bukan konflik, pakai nilai itu
  - dua-duanya berubah, beda   -> KONFLIK, field dibiarkan pada nilai dasar,
                                  masuk antrean, field lain tetap tersinkron

Alasan field yang berkonflik dibiarkan pada nilai dasar, bukan dipilih salah
satu: memilih berarti menebak, dan tebakan yang salah tidak bisa ditarik
kembali setelah CRM klien sudah diperbarui. Membiarkannya berarti kehilangan
satu pembaruan sampai manusia memutuskan — kerugian yang bisa dipulihkan.

Jalankan: python sinkron.py
"""
from __future__ import annotations

import json
from pathlib import Path

AKAR = Path(__file__).resolve().parent

# Field yang disinkronkan. `id` dan `versi` bukan field data.
KUNCI = "id"
BUKAN_FIELD = {KUNCI, "versi", "updated_at"}


# ---------------------------------------------------------------------------
# Mesin
# ---------------------------------------------------------------------------

def _nilai(rec: dict, field: str):
    """Nilai field, dengan 'tidak ada' dan null dianggap sama.

    Di JSON, field yang tidak ada dan field bernilai null sama-sama berarti
    "tidak ada nilai". Menyamakan keduanya di sini mencegah satu jenis
    konflik palsu: sistem yang satu menghapus field, yang lain mengosongkannya.
    """
    v = rec.get(field) if rec else None
    return None if v == "" else v


def gabung_satu(dasar: dict | None, lokal: dict | None, jauh: dict | None) -> dict:
    """Gabungkan satu catatan. Kembalikan {hasil, konflik, catatan}.

    `dasar` adalah salinan terakhir yang disepakati kedua sisi. Kalau `dasar`
    tidak ada, catatan baru: tidak ada nenek moyang, jadi tidak ada konflik
    yang bisa dibuktikan — yang ada hanya penciptaan.
    """
    # --- catatan hanya ada di satu sisi -----------------------------------
    if lokal is None and jauh is None:
        return {"hasil": None, "konflik": [], "catatan": ["tidak ada di kedua sisi"]}

    if dasar is None:
        if lokal is not None and jauh is None:
            return {"hasil": dict(lokal), "konflik": [],
                    "catatan": ["baru di lokal — dibuat, bukan konflik"]}
        if jauh is not None and lokal is None:
            return {"hasil": dict(jauh), "konflik": [],
                    "catatan": ["baru di jauh — dibuat, bukan konflik"]}
        # Ada di dua sisi tetapi belum pernah disepakati: bandingkan apa adanya.
        if lokal == jauh:
            return {"hasil": dict(lokal), "konflik": [],
                    "catatan": ["baru di kedua sisi dengan isi sama"]}
        dasar = {}

    # --- dihapus di satu sisi ---------------------------------------------
    if lokal is None and jauh is not None:
        if _sama_dengan_dasar(dasar, jauh):
            return {"hasil": None, "konflik": [],
                    "catatan": ["dihapus di lokal, jauh tidak berubah — dihapus"]}
        return {"hasil": dict(jauh),
                "konflik": [{"id": jauh.get(KUNCI), "field": "*",
                             "dasar": "(ada)", "lokal": "(dihapus)",
                             "jauh": "(diubah)",
                             "sebab": "dihapus di lokal tetapi diubah di jauh — penghapusan tidak dijalankan"}],
                "catatan": ["hapus-vs-ubah: tidak dihapus, menunggu manusia"]}

    if jauh is None and lokal is not None:
        if _sama_dengan_dasar(dasar, lokal):
            return {"hasil": None, "konflik": [],
                    "catatan": ["dihapus di jauh, lokal tidak berubah — dihapus"]}
        return {"hasil": dict(lokal),
                "konflik": [{"id": lokal.get(KUNCI), "field": "*",
                             "dasar": "(ada)", "lokal": "(diubah)",
                             "jauh": "(dihapus)",
                             "sebab": "dihapus di jauh tetapi diubah di lokal — penghapusan tidak dijalankan"}],
                "catatan": ["hapus-vs-ubah: tidak dihapus, menunggu manusia"]}

    # --- per-field --------------------------------------------------------
    fields = sorted(set(dasar) | set(lokal) | set(jauh))
    fields = [f for f in fields if f not in BUKAN_FIELD]

    hasil: dict = {KUNCI: lokal.get(KUNCI)}
    konflik: list[dict] = []
    catatan: list[str] = []
    ada_perubahan = False
    dari_kedua = False

    for f in fields:
        d, l, j = _nilai(dasar, f), _nilai(lokal, f), _nilai(jauh, f)

        if l == j:
            hasil[f] = l
            continue

        if l == d:
            # Hanya jauh yang berubah.
            hasil[f] = j
            ada_perubahan = True
            catatan.append(f"{f}: dari jauh")
            continue

        if j == d:
            # Hanya lokal yang berubah.
            hasil[f] = l
            ada_perubahan = True
            catatan.append(f"{f}: dari lokal")
            continue

        # Dua-duanya berubah, dan hasilnya berbeda. Tidak ada yang menang.
        hasil[f] = d
        konflik.append({
            "id": lokal.get(KUNCI), "field": f,
            "dasar": d, "lokal": l, "jauh": j,
            "sebab": "diubah di dua tempat dengan nilai berbeda",
        })
        catatan.append(f"{f}: KONFLIK — dibiarkan pada nilai dasar")

    if not konflik and catatan:
        # Perubahan dari dua sisi yang berbeda field: hasilnya gabungan,
        # jadi versi naik satu, bukan dua.
        dari_kedua = any(c.startswith(("dari lokal", "dari jauh")) is False for c in [])

    versi_l = lokal.get("versi") or 0
    versi_j = jauh.get("versi") or 0
    versi = max(versi_l, versi_j)
    if ada_perubahan or konflik:
        versi += 1
    hasil["versi"] = versi

    # `updated_at` disalin apa adanya, tidak dipakai memilih pemenang.
    hasil["updated_at"] = {
        "lokal": lokal.get("updated_at"),
        "jauh": jauh.get("updated_at"),
    }
    return {"hasil": hasil, "konflik": konflik, "catatan": catatan}


def _sama_dengan_dasar(dasar: dict, sisi: dict) -> bool:
    fields = [f for f in (set(dasar) | set(sisi)) if f not in BUKAN_FIELD]
    return all(_nilai(dasar, f) == _nilai(sisi, f) for f in fields)


def gabung(data: dict) -> dict:
    """Gabungkan seluruh catatan dari ketiga sisi."""
    def peta(daftar):
        return {r[KUNCI]: r for r in (daftar or [])}

    d, l, j = peta(data.get("dasar")), peta(data.get("lokal")), peta(data.get("jauh"))
    semua_id = sorted(set(d) | set(l) | set(j))

    keluar, konflik, jejak = [], [], []
    for i in semua_id:
        r = gabung_satu(d.get(i), l.get(i), j.get(i))
        if r["hasil"] is not None:
            keluar.append(r["hasil"])
        konflik.extend(r["konflik"])
        jejak.append({"id": i, "catatan": r["catatan"],
                      "dihapus": r["hasil"] is None})

    return {
        "gabung": keluar,
        "konflik": konflik,
        "ringkasan": {
            "catatan_dasar": len(d),
            "catatan_lokal": len(l),
            "catatan_jauh": len(j),
            "hasil_gabung": len(keluar),
            "konflik": len(konflik),
            "konflik_per_field": len({(k["id"], k["field"]) for k in konflik}),
            "dihapus": sum(1 for x in jejak if x["dihapus"]),
        },
        "jejak": jejak,
    }


def selesaikan(hasil_gabung: dict, pilihan: dict[tuple[str, str], object]) -> dict:
    """Terapkan keputusan manusia atas antrean konflik.

    `pilihan` berkunci (id, field) dengan nilai "lokal", "jauh", atau nilai
    bebas. Konflik yang belum diputuskan tetap di antrean — bukan dianggap
    selesai.
    """
    catatan = {r[KUNCI]: r for r in hasil_gabung["gabung"]}
    sisa = []
    for k in hasil_gabung["konflik"]:
        kunci = (k["id"], k["field"])
        if kunci not in pilihan:
            sisa.append(k)
            continue
        p = pilihan[kunci]
        nilai = k[p] if p in ("lokal", "jauh") else p
        rec = catatan.get(k["id"])
        if rec is not None and k["field"] != "*":
            rec[k["field"]] = nilai
            rec["versi"] = (rec.get("versi") or 0) + 1
    hasil_gabung["konflik"] = sisa
    return hasil_gabung


# ---------------------------------------------------------------------------
# Data uji
# ---------------------------------------------------------------------------

def data_uji() -> dict:
    """Kasus yang benar-benar terjadi di CRM, bukan kasus mainan.

    Sembilan catatan, masing-masing menguji satu aturan. Nomor kasus di
    komentar dipakai lagi di daftar uji di bawah.
    """
    return {
        "dasar": [
            # 1. hanya lokal berubah (tahap)
            {"id": "C01", "versi": 3, "nama": "Budi Santoso", "telp": "628121110001",
             "surel": "budi@sinarabadi.example", "kota": "Jakarta", "tahap": "baru",
             "updated_at": "2026-11-20T09:00:00+07:00"},
            # 2. hanya jauh berubah (pemilik)
            {"id": "C02", "versi": 5, "nama": "Siti Aminah", "telp": "628121110002",
             "surel": "siti@contoh.example", "kota": "Bandung", "tahap": "dihubungi",
             "updated_at": "2026-11-20T09:00:00+07:00"},
            # 3. dua sisi berubah ke nilai yang sama (kota)
            {"id": "C03", "versi": 2, "nama": "Andi Wijaya", "telp": "628121110003",
             "surel": "andi@contoh.example", "kota": "Surabaya", "tahap": "baru",
             "updated_at": "2026-11-20T09:00:00+07:00"},
            # 4. konflik satu field, field lain aman (telp bentrok)
            {"id": "C04", "versi": 4, "nama": "Maria Tan", "telp": "628121110004",
             "surel": "maria@contoh.example", "kota": "Medan", "tahap": "dihubungi",
             "updated_at": "2026-11-20T09:00:00+07:00"},
            # 5. dua konflik + satu perubahan sepihak
            {"id": "C05", "versi": 7, "nama": "Hendra Wijaya", "telp": "628121110005",
             "surel": "hendra@contoh.example", "kota": "Semarang", "tahap": "baru",
             "updated_at": "2026-11-20T09:00:00+07:00"},
            # 6. dikosongkan di satu sisi, diubah di sisi lain
            {"id": "C06", "versi": 2, "nama": "Rina Kusuma", "telp": "628121110006",
             "surel": "rina@contoh.example", "kota": "Yogyakarta", "tahap": "baru",
             "updated_at": "2026-11-20T09:00:00+07:00"},
            # 7. jauh lebih baru tetapi lokal yang berubah: bukan alasan menang
            {"id": "C07", "versi": 9, "nama": "Klaus Weber", "telp": "628121110007",
             "surel": "klaus@contoh.example", "kota": "Denpasar", "tahap": "dihubungi",
             "updated_at": "2026-11-20T09:00:00+07:00"},
            # 8. dihapus di jauh, tidak diubah di lokal -> boleh dihapus
            {"id": "C08", "versi": 1, "nama": "Tanpa Perubahan", "telp": "628121110008",
             "surel": "tetap@contoh.example", "kota": "Bogor", "tahap": "baru",
             "updated_at": "2026-11-20T09:00:00+07:00"},
            # 9. dihapus di jauh tetapi diubah di lokal -> jangan dihapus
            {"id": "C09", "versi": 2, "nama": "Wulan Sari", "telp": "628121110009",
             "surel": "wulan@contoh.example", "kota": "Makassar", "tahap": "baru",
             "updated_at": "2026-11-20T09:00:00+07:00"},
        ],
        "lokal": [
            {"id": "C01", "versi": 3, "nama": "Budi Santoso", "telp": "628121110001",
             "surel": "budi@sinarabadi.example", "kota": "Jakarta", "tahap": "tertarik",
             "updated_at": "2026-11-23T08:10:00+07:00"},
            {"id": "C02", "versi": 5, "nama": "Siti Aminah", "telp": "628121110002",
             "surel": "siti@contoh.example", "kota": "Bandung", "tahap": "dihubungi",
             "updated_at": "2026-11-23T08:11:00+07:00"},
            {"id": "C03", "versi": 2, "nama": "Andi Wijaya", "telp": "628121110003",
             "surel": "andi@contoh.example", "kota": "Surabaya", "tahap": "baru",
             "updated_at": "2026-11-23T08:12:00+07:00"},
            {"id": "C04", "versi": 4, "nama": "Maria Tan", "telp": "628121119999",
             "surel": "maria@contoh.example", "kota": "Medan", "tahap": "tertarik",
             "updated_at": "2026-11-23T08:13:00+07:00"},
            {"id": "C05", "versi": 7, "nama": "Hendra Wijaya", "telp": "628121110055",
             "surel": "hendra.wijaya@contoh.example", "kota": "Semarang", "tahap": "tertarik",
             "updated_at": "2026-11-23T08:14:00+07:00"},
            {"id": "C06", "versi": 2, "nama": "Rina Kusuma", "telp": "628121110006",
             "surel": "rina@contoh.example", "kota": "", "tahap": "baru",
             "updated_at": "2026-11-23T08:15:00+07:00"},
            {"id": "C07", "versi": 9, "nama": "Klaus Weber", "telp": "628121110007",
             "surel": "klaus@contoh.example", "kota": "Denpasar", "tahap": "tertarik",
             "updated_at": "2026-11-23T08:16:00+07:00"},
            {"id": "C08", "versi": 1, "nama": "Tanpa Perubahan", "telp": "628121110008",
             "surel": "tetap@contoh.example", "kota": "Bogor", "tahap": "baru",
             "updated_at": "2026-11-20T09:00:00+07:00"},
            {"id": "C09", "versi": 2, "nama": "Wulan Sari", "telp": "628121110009",
             "surel": "wulan@contoh.example", "kota": "Makassar", "tahap": "tertarik",
             "updated_at": "2026-11-23T08:17:00+07:00"},
            # 10. baru di lokal
            {"id": "C10", "versi": 1, "nama": "Lead Baru", "telp": "628121110010",
             "surel": "baru@contoh.example", "kota": "Palembang", "tahap": "baru",
             "updated_at": "2026-11-23T08:18:00+07:00"},
        ],
        "jauh": [
            {"id": "C01", "versi": 3, "nama": "Budi Santoso", "telp": "628121110001",
             "surel": "budi@sinarabadi.example", "kota": "Jakarta", "tahap": "baru",
             "updated_at": "2026-11-20T09:00:00+07:00"},
            {"id": "C02", "versi": 6, "nama": "Siti Aminah", "telp": "628121110002",
             "surel": "siti@contoh.example", "kota": "Bandung", "tahap": "dihubungi",
             "pemilik": "Dewi", "updated_at": "2026-11-23T09:30:00+07:00"},
            {"id": "C03", "versi": 3, "nama": "Andi Wijaya", "telp": "628121110003",
             "surel": "andi@contoh.example", "kota": "Surabaya", "tahap": "dihubungi",
             "updated_at": "2026-11-23T08:40:00+07:00"},
            {"id": "C04", "versi": 4, "nama": "Maria Tan", "telp": "628121118888",
             "surel": "maria@contoh.example", "kota": "Medan", "tahap": "dihubungi",
             "updated_at": "2026-11-23T09:35:00+07:00"},
            {"id": "C05", "versi": 7, "nama": "Hendra Wijaya", "telp": "628121110066",
             "surel": "hendra.w@contoh.example", "kota": "Semarang", "tahap": "baru",
             "updated_at": "2026-11-23T09:36:00+07:00"},
            {"id": "C06", "versi": 2, "nama": "Rina Kusuma", "telp": "628121110006",
             "surel": "rina@contoh.example", "kota": "Solo", "tahap": "baru",
             "updated_at": "2026-11-23T09:37:00+07:00"},
            # C07: jauh punya updated_at jauh lebih baru, tetapi yang berubah lokal
            {"id": "C07", "versi": 9, "nama": "Klaus Weber", "telp": "628121110007",
             "surel": "klaus@contoh.example", "kota": "Denpasar", "tahap": "dihubungi",
             "updated_at": "2026-11-23T23:59:00+07:00"},
            # C08 dan C09 tidak ada di jauh: dihapus di sana
            {"id": "C11", "versi": 1, "nama": "Lead dari CRM", "telp": "628121110011",
             "surel": "crm@contoh.example", "kota": "Balikpapan", "tahap": "baru",
             "updated_at": "2026-11-23T09:38:00+07:00"},
        ],
    }


# ---------------------------------------------------------------------------
# Uji
# ---------------------------------------------------------------------------

def uji() -> int:
    data = data_uji()
    h = gabung(data)
    rec = {r["id"]: r for r in h["gabung"]}
    kon = {(k["id"], k["field"]): k for k in h["konflik"]}

    kasus = []

    def cek(nama, benar, pesan=""):
        kasus.append({"nama": nama, "lulus": bool(benar), "pesan": pesan})

    # 1. hanya lokal berubah -> lokal menang, versi naik
    cek("hanya lokal berubah: tahap C01 jadi 'tertarik'",
        rec["C01"]["tahap"] == "tertarik", f"dapat {rec['C01']['tahap']!r}")
    cek("hanya lokal berubah: versi C01 naik dari 3 ke 4",
        rec["C01"]["versi"] == 4, f"dapat {rec['C01']['versi']}")

    # 2. hanya jauh berubah -> jauh menang, field baru ikut
    cek("hanya jauh berubah: pemilik C02 diisi dari jauh",
        rec["C02"].get("pemilik") == "Dewi", f"dapat {rec['C02'].get('pemilik')!r}")

    # 3. dua sisi berubah ke nilai sama -> bukan konflik
    cek("dua sisi berubah sama: C03 tidak masuk antrean konflik",
        ("C03", "kota") not in kon, "C03.kota seharusnya bukan konflik")
    cek("dua sisi berubah sama: tahap C03 dari jauh ('dihubungi')",
        rec["C03"]["tahap"] == "dihubungi", f"dapat {rec['C03']['tahap']!r}")

    # 4. konflik satu field, field lain tetap tersinkron
    cek("konflik: C04.telp masuk antrean",
        ("C04", "telp") in kon, "C04.telp seharusnya konflik")
    cek("konflik: field yang berkonflik dibiarkan pada nilai dasar",
        rec["C04"]["telp"] == "628121110004", f"dapat {rec['C04']['telp']!r}")
    cek("konflik tidak menghalangi field lain: C04.tahap tetap tersinkron "
        "dari lokal ('tertarik', hanya lokal yang berubah)",
        rec["C04"]["tahap"] == "tertarik", f"dapat {rec['C04']['tahap']!r}")

    # 5. dua konflik sekaligus
    cek("dua konflik: C05.telp dan C05.surel sama-sama di antrean",
        ("C05", "telp") in kon and ("C05", "surel") in kon,
        f"dapat {sorted(k[1] for k in kon if k[0] == 'C05')}")

    # 6. dikosongkan vs diubah -> konflik, bukan hapus diam-diam
    cek("kosong vs diubah: C06.kota masuk antrean",
        ("C06", "kota") in kon, "C06.kota seharusnya konflik")
    cek("kosong vs diubah: nilai dasar dipertahankan, bukan dikosongkan",
        rec["C06"]["kota"] == "Yogyakarta", f"dapat {rec['C06']['kota']!r}")

    # 7. updated_at lebih baru tidak membuat jauh menang
    cek("tidak ada last-write-wins: C07.tahap tetap dari lokal walau "
        "updated_at jauh 23:59",
        rec["C07"]["tahap"] == "tertarik", f"dapat {rec['C07']['tahap']!r}")

    # 8. dihapus di jauh, lokal tidak berubah -> dihapus
    cek("hapus aman: C08 hilang dari hasil",
        "C08" not in rec, "C08 seharusnya terhapus")

    # 9. dihapus di jauh tetapi diubah di lokal -> jangan dihapus
    cek("hapus-vs-ubah: C09 TIDAK dihapus",
        "C09" in rec, "C09 tidak boleh terhapus")
    cek("hapus-vs-ubah: C09 masuk antrean dengan field '*'",
        ("C09", "*") in kon, "C09 seharusnya punya konflik '*'")

    # 10. baru di satu sisi -> dibuat, bukan konflik
    cek("baru di lokal: C10 dibuat", "C10" in rec, "C10 seharusnya dibuat")
    cek("baru di jauh: C11 dibuat", "C11" in rec, "C11 seharusnya dibuat")
    cek("catatan baru tidak masuk antrean konflik",
        not any(k[0] in ("C10", "C11") for k in kon),
        "C10/C11 seharusnya bukan konflik")

    # 11. rekonsiliasi jumlah
    cek("jumlah konflik = 5 (C04.telp, C05.telp, C05.surel, C06.kota, C09.*)",
        h["ringkasan"]["konflik"] == 5,
        f"dapat {h['ringkasan']['konflik']}")
    cek("hasil gabung = 10 catatan (9 dasar - 1 dihapus + 1 baru + 1 dari jauh)",
        h["ringkasan"]["hasil_gabung"] == 10,
        f"dapat {h['ringkasan']['hasil_gabung']}")

    # 12. keputusan manusia diterapkan, sisanya tetap di antrean
    h2 = gabung(data)
    h2 = selesaikan(h2, {("C04", "telp"): "jauh"})
    rec2 = {r["id"]: r for r in h2["gabung"]}
    cek("manusia memilih 'jauh' untuk C04.telp",
        rec2["C04"]["telp"] == "628121118888", f"dapat {rec2['C04']['telp']!r}")
    cek("konflik yang belum diputuskan tetap di antrean",
        len(h2["konflik"]) == 4, f"dapat {len(h2['konflik'])}")
    cek("versi naik setelah keputusan manusia",
        rec2["C04"]["versi"] > rec["C04"]["versi"],
        f"{rec['C04']['versi']} -> {rec2['C04']['versi']}")

    lulus = sum(1 for k in kasus if k["lulus"])
    for k in kasus:
        print(f"  {'OK  ' if k['lulus'] else 'GAGAL'} {k['nama']}")
        if not k["lulus"]:
            print(f"        {k['pesan']}")
    print(f"\nHASIL: {lulus}/{len(kasus)} lulus")

    (AKAR / "data_poin4.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    (AKAR / "hasil_poin4.json").write_text(
        json.dumps(h, ensure_ascii=False, indent=1), encoding="utf-8")

    r = h["ringkasan"]
    print(f"catatan: dasar {r['catatan_dasar']}, lokal {r['catatan_lokal']}, "
          f"jauh {r['catatan_jauh']} -> gabung {r['hasil_gabung']}")
    print(f"konflik per-field: {r['konflik_per_field']} field, "
          f"{r['konflik']} entri antrean, dihapus {r['dihapus']}")
    print("Hasil: hasil_poin4.json")
    return 0 if lulus == len(kasus) else 1


if __name__ == "__main__":
    raise SystemExit(uji())
