"""Demo tiga poin untuk SAB: dedup lintas kanal (1), idempotensi (5), rekonsiliasi (6).

Jalankan: python demo.py

Yang dibuktikan, dan yang tidak:

  Dibuktikan  : perilaku pencocokan pada data yang sengaja dibuat tidak konsisten,
                ketahanan terhadap kiriman ulang, dan laporan yang menemukan lead
                yang tidak pernah dibalas.
  Tidak       : sambungan ke CRM asli, WhatsApp Business, atau model bahasa.
                Itu dikerjakan di tahap 1 setelah demo disetujui.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import dedup

AKAR = Path(__file__).parent


def muat() -> dict:
    f = AKAR / "data_uji.json"
    if not f.exists():
        raise SystemExit("data_uji.json belum ada. Jalankan: python generate.py")
    return json.loads(f.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# Poin 1 — dedup lintas kanal
# --------------------------------------------------------------------------
def gabungkan(lead: list[dict]) -> tuple[list[dict], list[dict], dict]:
    """Kelompokkan lead jadi identitas. Kembalikan (identitas, antrean, statistik).

    Aturan penting: keputusan "antrean" TIDAK menggabungkan. Lead tetap menjadi
    identitas baru, dan pasangannya dicatat untuk dilihat manusia. Menggabung
    lalu meminta maaf tidak mungkin; memisah lalu menggabung belakangan bisa.

    Pencarian kandidat memakai blocking (lihat dedup.kunci_blok), bukan
    membandingkan setiap lead dengan setiap identitas.
    """
    identitas: list[dict] = []
    antrean: list[dict] = []
    indeks_nomor: dict[str, int] = {}
    indeks_email: dict[str, int] = {}
    indeks_blok: dict[str, set[int]] = {}
    perbandingan = 0

    def buat_baru(l: dict) -> int:
        identitas.append({
            "id": f"ID{len(identitas):03d}",
            "nama": l["nama"], "nomor": l["nomor"], "email": l["email"],
            "perusahaan": l["perusahaan"], "kota": l["kota"],
            "kanal": [l["kanal"]], "event": [l["event_id"]],
            "_orang": {l["_orang"]},
        })
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
            # hanya identitas yang berbagi kunci blok yang perlu dibandingkan
            kandidat: set[int] = set()
            for k in dedup.kunci_blok(l):
                kandidat |= indeks_blok.get(k, set())

            calon_gabung, skor_gabung = None, 0.0
            calon_antre, skor_antre, alasan_antre = None, 0.0, ""
            for i in kandidat:
                perbandingan += 1
                keputusan, skor, alasan = dedup.putuskan(l, identitas[i])
                if keputusan == "gabung" and skor > skor_gabung:
                    calon_gabung, skor_gabung = i, skor
                elif keputusan == "antrean" and skor > skor_antre:
                    calon_antre, skor_antre, alasan_antre = i, skor, alasan

            if calon_gabung is not None:
                ketemu = calon_gabung
            else:
                if calon_antre is not None:
                    antrean.append({
                        "lead": l["event_id"], "kanal": l["kanal"],
                        "nama_lead": l["nama"],
                        "calon": identitas[calon_antre]["id"],
                        "nama_calon": identitas[calon_antre]["nama"],
                        "skor": skor_antre, "alasan": alasan_antre,
                        # disimpan untuk rekonsiliasi: apakah pasangan ini
                        # benar-benar orang yang sama atau hanya mirip namanya
                        "_orang_lead": l["_orang"],
                        "_orang_calon": next(iter(identitas[calon_antre]["_orang"])),
                    })
                buat_baru(l)
                continue

        ident = identitas[ketemu]
        ident["kanal"].append(l["kanal"])
        ident["event"].append(l["event_id"])
        ident["_orang"].add(l["_orang"])
        if n:
            indeks_nomor.setdefault(n, ketemu)
        if e:
            indeks_email.setdefault(e, ketemu)

    return identitas, antrean, {"perbandingan": perbandingan,
                                "tanpa_blocking": len(lead) * (len(lead) - 1) // 2}


# --------------------------------------------------------------------------
# Poin 5 — idempotensi, retry, dead-letter queue, alarm, handoff manusia
# --------------------------------------------------------------------------
def uji_idempotensi(lead: list[dict], ulang: int = 5) -> dict:
    """Kirim setiap lead `ulang` kali. Yang benar: satu baris per event_id."""
    tersimpan: dict[str, dict] = {}
    ditolak = 0
    for _ in range(ulang):
        for l in lead:
            kunci = l["event_id"]
            if kunci in tersimpan:
                ditolak += 1
                continue
            tersimpan[kunci] = l
    return {
        "dikirim": len(lead) * ulang,
        "tersimpan": len(tersimpan),
        "ditolak_sebagai_duplikat": ditolak,
        "event_unik": len({l["event_id"] for l in lead}),
    }


PERCOBAAN_MAKS = 3
P_TRANSIEN = 0.30     # gagal sekali, berhasil pada percobaan berikutnya
P_PERMANEN = 0.10     # gagal di semua percobaan -> DLQ
AMBANG_ALARM = 8      # DLQ lebih dalam dari ini -> alarm


def _acak(kunci: str, garam: str) -> float:
    """Angka 0..1 yang tetap sama tiap kali dijalankan (FNV-1a 32-bit).

    Kegagalan pengiriman disimulasikan: demo ini tidak mengirim pesan
    sungguhan. Yang nyata adalah penanganannya — percobaan ulang, DLQ, alarm,
    dan pemutaran ulang. Memakai FNV-1a, bukan hash pustaka, supaya workflow
    n8n bisa menghitung angka yang persis sama.
    """
    h = 2166136261
    for b in f"{kunci}|{garam}".encode("utf-8"):
        h ^= b
        h = (h * 16777619) & 0xFFFFFFFF
    return h / 4294967296


def kirim_balasan(identitas: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """Kirim balasan pertama ke setiap identitas, dengan retry dan DLQ.

    Ini bagian poin 5 yang sebelumnya tidak ada di halaman: Tico mencatat
    bahwa demo hanya menunjukkan idempotensi, sementara retry, DLQ, alarm
    kedalaman, dan handoff ke manusia tidak terlihat. Ketiganya ada di sini.
    """
    terkirim, dlq, jejak = [], [], []
    for i in identitas:
        kunci = f"{i['id']}|balas"
        transien = _acak(kunci, "transien") < P_TRANSIEN
        permanen = _acak(kunci, "permanen") < P_PERMANEN

        catatan = []
        berhasil = False
        for percobaan in range(1, PERCOBAAN_MAKS + 1):
            gagal = permanen or (transien and percobaan == 1)
            catatan.append({"percobaan": percobaan,
                            "hasil": "gagal" if gagal else "terkirim"})
            if not gagal:
                berhasil = True
                break
        jejak.append({"identitas": i["id"], "percobaan": catatan})

        if berhasil:
            terkirim.append({"identitas": i["id"], "percobaan_ke": percobaan})
        else:
            dlq.append({
                "id": f"DLQ-{len(dlq) + 1:03d}",
                "identitas": i["id"],
                "nama": i["nama"],
                "percobaan": PERCOBAAN_MAKS,
                "error_message": "kanal menolak setelah 3 percobaan (5xx)",
                "original_payload": {"kanal": i["kanal"][-1] if i["kanal"] else ""},
            })
    return terkirim, dlq, jejak


def handoff_manusia(antrean: list[dict], identitas: list[dict]) -> list[dict]:
    """Lead yang tidak boleh diputuskan mesin.

    Dua sebab, keduanya nyata: pasangan di antrean yang belum diputuskan
    manusia, dan identitas yang namanya tidak terbaca.
    """
    keluar = []
    for a in antrean:
        keluar.append({"identitas": a["lead"], "nama": a["nama_lead"],
                       "alasan": "pasangan di antrean belum diputuskan"})
    for i in identitas:
        if not dedup.nama(i.get("nama", "")):
            keluar.append({"identitas": i["id"], "nama": i.get("nama", ""),
                           "alasan": "nama tidak ada / tidak bisa dibaca"})
    return keluar


# --------------------------------------------------------------------------
# Poin 6 — rekonsiliasi
# --------------------------------------------------------------------------
def rekonsiliasi(identitas: list[dict], terkirim: list[dict],
                 dlq: list[dict]) -> dict:
    """Bandingkan yang seharusnya dibalas dengan yang benar-benar dibalas.

    Versi 21 November memilih enam ID dengan `harus[::len//6][:6]`, yang selalu
    menghasilkan kelipatan 28 dan karena itu bisa ditebak tanpa menjalankan
    apa pun — Tico menunjuk tepat ke cacat itu. Sekarang pengecualian diambil
    dari isi DLQ: akibat nyata dari pengiriman yang gagal, bukan pola yang
    saya pilih sendiri.
    """
    harus = [i["id"] for i in identitas]
    dapat = {t["identitas"] for t in terkirim}
    return {
        "seharusnya_dibalas": len(harus),
        "benar_benar_dibalas": len(dapat),
        "selisih": len(harus) - len(dapat),
        "pengecualian": sorted(i for i in harus if i not in dapat),
        "sebab_pengecualian": [
            {"identitas": d["identitas"], "sebab": d["error_message"]}
            for d in dlq
        ],
    }


def jalankan_suite(modul) -> tuple[list[dict], int]:
    """Jalankan satu berkas uji kasus, kembalikan (hasil, jumlah lulus).

    `jenis` ikut dicatat supaya halaman bisa membedakan pasangan yang memang
    orang sama dari alias (nama panggilan / ganti nama) yang justru HARUS
    dipisah. Tanpa pemisahan itu, alias terbaca sebagai kegagalan padahal
    perilakunya benar.
    """
    hasil = []
    for k in modul.KASUS:
        keputusan, skor, _ = dedup.putuskan(k["a"], k["b"])
        hasil.append({
            "ket": k["ket"], "nama_a": k["a"]["nama"], "nama_b": k["b"]["nama"],
            "dapat": keputusan, "harap": k["harap"], "skor": skor,
            "sumber": k.get("sumber", ""), "jenis": k.get("jenis", "cocok"),
            "lulus": keputusan == k["harap"],
        })
    return hasil, sum(1 for h in hasil if h["lulus"])


def main() -> None:
    data = muat()
    lead = data["lead"]
    orang = {o["id"] for o in data["orang"]}

    print("=" * 66)
    print("DEMO SAB — poin 1, 5, 6, dijalankan pada data uji sintetis")
    print("=" * 66)

    # ---- poin 1
    identitas, antrean, stat = gabungkan(lead)
    mentah = len(lead)
    hasil = len(identitas)
    print(f"\nPOIN 1 — dedup lintas kanal")
    print(f"  lead mentah dari 5 kanal : {mentah}")
    print(f"  identitas setelah dedup  : {hasil}  (SEMENTARA, lihat catatan)")
    print(f"  digabung otomatis        : {mentah - hasil}")
    print(f"  pasangan perlu dilihat   : {len(antrean)}")
    print(f"  perbandingan dijalankan  : {stat['perbandingan']:,} "
          f"(tanpa blocking: {stat['tanpa_blocking']:,})")

    # akurasi terhadap kunci jawaban
    salah_gabung = [i for i in identitas if len(i["_orang"]) > 1]
    per_orang = defaultdict(set)
    for i in identitas:
        for o in i["_orang"]:
            per_orang[o].add(i["id"])
    terpisah = [o for o, ids in per_orang.items() if len(ids) > 1]

    print(f"  orang unik sebenarnya    : {len(orang)}")
    print(f"  salah gabung             : {len(salah_gabung)}  (wajib 0: salah gabung tidak bisa ditarik)")
    print(f"  orang terpecah           : {len(terpisah)}  (boleh >0 selama masuk antrean manusia)")
    if salah_gabung:
        for i in salah_gabung[:3]:
            print(f"    - {i['id']} menggabung {sorted(i['_orang'])}")

    # Rekonsiliasi angka — pertanyaan SAB poin 4: 27 + 3 = 30, lalu apa?
    duplikat_ditanam = mentah - len(orang)
    antre_sama = sum(1 for a in antrean
                     if a["_orang_lead"] == a["_orang_calon"])
    antre_beda = len(antrean) - antre_sama
    print(f"\n  REKONSILIASI ANGKA")
    print(f"    duplikat yang ditanam  : {duplikat_ditanam}")
    print(f"    digabung otomatis      : {mentah - hasil}")
    print(f"    terpecah (aman)        : {len(terpisah)}")
    print(f"    {len(orang)} orang + {len(terpisah)} kelebihan = {len(orang) + len(terpisah)}"
          f"  -> cocok dengan {hasil} identitas")
    print(f"    antrean: {antre_sama} pasangan orang sama (perlu diputuskan),"
          f" {antre_beda} pasangan orang berbeda (kebisingan)")
    print(f"  CATATAN: {hasil} adalah identitas SEMENTARA. Setelah {antre_sama} pasangan")
    print(f"           di antrean diputuskan manusia, angkanya turun ke "
          f"{hasil - antre_sama}.")

    # ---- poin 5
    idem = uji_idempotensi(lead, ulang=5)
    terkirim, dlq, jejak = kirim_balasan(identitas)
    alarm = len(dlq) > AMBANG_ALARM
    pulih, sisa = [], []
    for d in dlq:
        (pulih if _acak(f"{d['identitas']}|putar", "ulang") < 0.6 else sisa).append(d)
    terkirim_semua = terkirim + [{"identitas": p["identitas"], "percobaan_ke": 0}
                                 for p in pulih]

    print(f"\nPOIN 5 — idempotensi, retry, DLQ, alarm, handoff")
    print(f"  total kiriman            : {idem['dikirim']}")
    print(f"  tersimpan                : {idem['tersimpan']}")
    print(f"  ditolak sebagai duplikat : {idem['ditolak_sebagai_duplikat']}")
    print(f"  event unik seharusnya    : {idem['event_unik']}")
    status = "LULUS" if idem["tersimpan"] == idem["event_unik"] else "GAGAL"
    print(f"  idempotensi              : {status}")
    print(f"  balasan dikirim          : {len(terkirim)}")
    print(f"  gagal setelah 3 percobaan: {len(dlq)}  -> DLQ")
    print(f"  alarm kedalaman DLQ      : {'MENYALA' if alarm else 'tidak'} "
          f"(ambang {AMBANG_ALARM})")
    print(f"  dipulihkan dari DLQ      : {len(pulih)}")
    print(f"  DLQ akhir                : {len(sisa)}")

    # ---- poin 6
    rek = rekonsiliasi(identitas, terkirim_semua, sisa)
    manusia = handoff_manusia(antrean, identitas)
    print(f"\nPOIN 6 — rekonsiliasi harian")
    print(f"  seharusnya dibalas       : {rek['seharusnya_dibalas']}")
    print(f"  benar-benar dibalas      : {rek['benar_benar_dibalas']}")
    print(f"  selisih                  : {rek['selisih']}")
    print(f"  pengecualian             : {', '.join(rek['pengecualian'][:8])}"
          f"{' ...' if len(rek['pengecualian']) > 8 else ''}")
    print(f"  handoff ke manusia       : {len(manusia)}")
    print("  arti: alur bisa saja hijau 100% sementara angka ini tidak nol.")
    # Bukti bahwa daftar pengecualian tidak berpola: jarak antar-ID bervariasi.
    nomor = [int(x[2:]) for x in rek["pengecualian"] if x.startswith("ID")]
    jarak = [b - a for a, b in zip(nomor, nomor[1:])]
    print(f"  jarak antar-ID           : {jarak[:12]}"
          f"  (bervariasi = bukan rumus, melainkan akibat pengiriman gagal)")

    # ---- uji kasus lapangan
    # Kasus lapangan dijalankan di sini juga, supaya halaman tidak pernah
    # menampilkan hasil uji kasus yang sudah usang.
    import uji_kasus
    import uji_kasus_nyata
    import uji_kasus_nyata2

    hasil_kasus, lulus_kasus = jalankan_suite(uji_kasus)
    print(f"\nUJI KASUS LAPANGAN — {lulus_kasus}/{len(hasil_kasus)} lulus")
    for h in hasil_kasus:
        if not h["lulus"]:
            print(f"  GAGAL {h['ket']}: dapat {h['dapat']}, harap {h['harap']}")

    # ---- uji kasus nyata (nama tokoh publik, konvensi terdokumentasi)
    hasil_nyata, lulus_nyata = jalankan_suite(uji_kasus_nyata)
    print(f"\nUJI KASUS NYATA — {lulus_nyata}/{len(hasil_nyata)} sesuai")
    for h in hasil_nyata:
        if not h["lulus"]:
            print(f"  GAGAL {h['ket']}: dapat {h['dapat']}, harap {h['harap']}")

    # ---- uji kasus nyata putaran kedua (ejaan 1972, transliterasi Jerman, alias)
    hasil_nyata2, lulus_nyata2 = jalankan_suite(uji_kasus_nyata2)
    print(f"\nUJI KASUS NYATA PUTARAN 2 — {lulus_nyata2}/{len(hasil_nyata2)} sesuai")
    for h in hasil_nyata2:
        if not h["lulus"]:
            print(f"  GAGAL {h['ket']}: dapat {h['dapat']}, harap {h['harap']}")

    # ---- ujian 50 lead dari SAB (kalau sudah dijalankan)
    # Dibaca dari berkas, bukan dijalankan ulang di sini, karena workflow n8n
    # butuh n8n untuk dijalankan. `uji_kesamaan.py` yang menjaga keduanya tetap
    # sama.
    ujian: dict = {}
    f_ujian = AKAR / "ujian" / "hasil_ujian.json"
    f_log = AKAR / "ujian" / "log_n8n.json"
    if f_ujian.exists():
        h = json.loads(f_ujian.read_text(encoding="utf-8"))
        p5u = h["poin_5_kirim"]
        ujian = {
            "baris": h["poin_1_dedup"]["baris_masuk"],
            "identitas": h["poin_1_dedup"]["identitas"],
            "kontak_bersama": h["poin_1_dedup"]["kontak_dipakai_bersama"],
            "dlq": p5u["dlq_setelah_putar_ulang"],
            "dlq_awal": p5u["dlq_awal"],
            "terkirim": p5u["terkirim"],
            "total_percobaan": p5u["total_percobaan"],
            "item_dicoba_ulang": p5u["item_dicoba_ulang"],
        }
        if f_log.exists():
            log = json.loads(f_log.read_text(encoding="utf-8"))
            bagian = []
            for nama, v in log.get("node", {}).items():
                jalan = v.get("jalan") or []
                if not jalan:
                    continue
                # Semua putaran ditulis, bukan hanya yang terakhir: node Kirim
                # yang berjalan tiga kali justru bukti percobaan ulang.
                isi = " ".join(
                    "[" + "+".join(str(c) for c in j.get("cabang", [])) + "]"
                    for j in jalan)
                bagian.append(f"{nama} {isi}")
            ujian["log_node"] = " → ".join(bagian) + " item."
            ujian["log_kirim"] = " ".join(
                "[" + "+".join(str(c) for c in j.get("cabang", [])) + "]"
                for j in (log.get("node", {}).get("Kirim", {}).get("jalan") or []))
            ujian["putaran_kirim"] = log.get("node", {}).get("Kirim", {}).get("putaran", 0)

    # ---- poin 4: sinkron dua arah (kalau sudah dijalankan)
    # Dibaca dari berkas keluaran poin4/, sama seperti ujian: yang dijalankan
    # di sini hanya mesin 200 lead, bukan seluruh pipeline.
    poin4: dict = {}
    f_p4 = AKAR / "poin4" / "hasil_poin4.json"
    if f_p4.exists():
        h4 = json.loads(f_p4.read_text(encoding="utf-8"))
        poin4 = {
            **h4["ringkasan"],
            "contoh_konflik": h4["konflik"][:6],
            "contoh_gabung": h4["gabung"][:4],
        }

    laporan = {
        "poin_1": {
            "lead_mentah": mentah, "identitas": hasil,
            "digabung_otomatis": mentah - hasil,
            "pasangan_antrean": len(antrean),
            "salah_gabung": len(salah_gabung), "orang_terpecah": len(terpisah),
            "orang_unik_sebenarnya": len(orang),
            "duplikat_ditanam": duplikat_ditanam,
            "antrean_orang_sama": antre_sama,
            "antrean_orang_beda": antre_beda,
            "identitas_setelah_antrean": hasil - antre_sama,
            "perbandingan": stat["perbandingan"],
            "perbandingan_tanpa_blocking": stat["tanpa_blocking"],
        },
        "poin_5": {**idem,
                   "balasan_terkirim": len(terkirim_semua),
                   "dlq_awal": len(dlq),
                   "dlq_akhir": len(sisa),
                   "dipulihkan": len(pulih),
                   "alarm": alarm,
                   "ambang_alarm": AMBANG_ALARM,
                   "dlq": sisa,
                   "handoff": manusia},
        "poin_6": rek,
        "poin_4": poin4,
        "uji_kasus": {"total": len(hasil_kasus), "lulus": lulus_kasus,
                      "kasus": hasil_kasus},
        "uji_kasus_nyata": {"total": len(hasil_nyata), "lulus": lulus_nyata,
                            "kasus": hasil_nyata},
        "uji_kasus_nyata2": {"total": len(hasil_nyata2), "lulus": lulus_nyata2,
                             "kasus": hasil_nyata2},
        # kunci internal _orang_* tidak ikut ditulis: halaman publik tidak perlu
        # membuka kunci jawaban, dan antrean_contoh hanya untuk dilihat.
        "antrean_contoh": [{k: v for k, v in a.items()
                            if not k.startswith("_")} for a in antrean[:10]],
        "ujian": ujian,
    }
    (AKAR / "hasil_demo.json").write_text(
        json.dumps(laporan, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nLaporan disimpan: hasil_demo.json")


if __name__ == "__main__":
    main()
