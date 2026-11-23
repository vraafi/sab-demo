"""Mesin enam poin untuk ujian 50 lead dari SAB.

Ini implementasi rujukan (Python). Workflow n8n di `workflow_ujian.json`
menjalankan logika yang sama; hasil keduanya harus identik, dan itu yang
menjawab pertanyaan Tico nomor 7 (Python atau n8n).

Enam poin yang dikerjakan, sesuai surat Tico 20 November:

  1. Lima kanal -> satu pipeline, dedup lintas kanal saat nama/nomor/email
     tidak konsisten.
  2. Kualifikasi + balasan pertama, bahasa ditentukan dari isi pesan
     (ID/EN/DE), bukan dari kanal.
  3. Follow-up berhenti lintas kanal; opt-out di satu kanal berlaku di semua.
  4. (Sinkron CRM dua arah — diuji terpisah di `crm.py`, bukan di sini.)
  5. Idempotensi, retry, dead-letter queue, alarm kedalaman, handoff manusia.
  6. Rekonsiliasi harian: yang seharusnya dibalas vs yang benar-benar dibalas.

Perbedaan penting dengan versi 21 November: daftar pengecualian rekonsiliasi
TIDAK dihitung dengan rumus indeks. Ia keluar dari isi DLQ, yaitu akibat nyata
dari pengiriman yang gagal. Versi lama memakai `harus[::len//6][:6]`, yang
selalu menghasilkan kelipatan 28 dan karena itu bisa ditebak tanpa menjalankan
apa pun — persis yang ditunjuk Tico.

Jalankan: python mesin.py
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

AKAR = Path(__file__).resolve().parent
sys.path.insert(0, str(AKAR.parent))
import dedup  # noqa: E402  logika nama yang sudah diuji di demo

CSV_MASUK = AKAR.parent.parent / "marketing" / "sab" / "SAB_test_leads_50.csv"

# ---------------------------------------------------------------------------
# 1. Normalisasi
# ---------------------------------------------------------------------------

def telp(s: str) -> str:
    """Nomor ke bentuk E.164 tanpa tanda plus.

    Aturan yang dipakai, dan alasannya:
    - `0049…` adalah awalan internasional gaya Eropa; `+49…` bentuk lain dari
      hal yang sama. Keduanya harus bertemu.
    - `0…` di Indonesia berarti nomor lokal: `0812…` -> `62812…`,
      `021…` (Jakarta, kabel) -> `6221…`.
    - Nomor yang sudah diawali kode negara (62, 65, 49, 1) dibiarkan.
    """
    d = re.sub(r"\D", "", s or "")
    if not d:
        return ""
    if d.startswith("00"):
        d = d[2:]
    if d.startswith("0"):
        d = "62" + d[1:]
    elif d.startswith("8") and len(d) >= 9:
        d = "62" + d
    return d


def surel(e: str) -> str:
    """Email: huruf kecil, buang +tag, buang titik hanya untuk Gmail.

    Titik tidak dibuang untuk domain lain karena di banyak penyedia
    `a.b@x` dan `ab@x` adalah dua kotak surat berbeda.

    Salah ketik domain TIDAK diperbaiki di sini. `gmial.example` dan
    `gmail.example` sengaja dibiarkan berbeda; pasangan seperti itu harus
    disatukan lewat nomor, bukan lewat tebakan ejaan domain.
    """
    e = (e or "").strip().lower()
    if "@" not in e:
        return ""
    lokal, domain = e.rsplit("@", 1)
    lokal = lokal.split("+", 1)[0]
    if domain in ("gmail.com", "googlemail.com"):
        lokal = lokal.replace(".", "")
    return f"{lokal}@{domain}"


def nama_bersih(n: str) -> list[str]:
    """Token nama tanpa gelar/sapaan, memakai logika yang sudah diuji di demo."""
    return dedup.nama(n or "")


def nama_cocok(a: str, b: str) -> bool:
    """Apakah dua nama cukup cocok untuk dianggap orang yang sama?

    Ini penjaga yang menjawab jebakan L020/L021. Joko Susilo dan Maria Tan
    berbagi email `info@sinarabadi.example` dan nomor kantor `021-5550-0111`.
    Email dan nomor yang sama TIDAK cukup: di Indonesia satu alamat kantor
    dipakai banyak orang. Kalau namanya tidak cocok, sistem tidak menggabung —
    ia menandai "kontak dipakai bersama" untuk diperiksa manusia.

    Aturan: cocok kalau berbagi satu kata nama, ATAU marganya mirip.
    """
    na, nb = nama_bersih(a), nama_bersih(b)
    if not na or not nb:
        return True          # tidak bisa dinilai; biarkan kunci lain memutuskan
    if set(na) & set(nb):
        return True
    if len(na) >= 2 and len(nb) >= 2:
        return dedup._mirip_token(na[-1], nb[-1]) >= 0.85
    # Satu kata vs banyak kata: "Dewi" vs "Dewi Anggraini" sudah tertangkap
    # himpunan kata di atas. "B. Santoso" vs "Budi Santoso" perlu jalur inisial.
    return dedup._mirip_token(na[0], nb[0]) >= 0.90


# ---------------------------------------------------------------------------
# 2. Dedup lintas kanal
# ---------------------------------------------------------------------------

class Gabung:
    """Union-find sederhana untuk mengelompokkan baris menjadi identitas."""

    def __init__(self, n: int) -> None:
        self.induk = list(range(n))

    def cari(self, i: int) -> int:
        while self.induk[i] != i:
            self.induk[i] = self.induk[self.induk[i]]
            i = self.induk[i]
        return i

    def satukan(self, a: int, b: int) -> None:
        ra, rb = self.cari(a), self.cari(b)
        if ra != rb:
            self.induk[rb] = ra


def kelompokkan(rows: list[dict]) -> tuple[list[dict], list[dict], dict]:
    """Kembalikan (identitas, antrean_kontak_bersama, statistik)."""
    n = len(rows)
    g = Gabung(n)

    # Indeks kontak -> daftar baris. Disimpan semua, bukan hanya yang pertama,
    # supaya benturan bisa diperiksa, bukan diam-diam diambil satu.
    per_telp: dict[str, list[int]] = defaultdict(list)
    per_surel: dict[str, list[int]] = defaultdict(list)
    per_isi: dict[str, list[int]] = defaultdict(list)

    for i, r in enumerate(rows):
        t, s = telp(r["phone"]), surel(r["email"])
        r["_telp"], r["_surel"] = t, s
        if t:
            per_telp[t].append(i)
        if s:
            per_surel[s].append(i)
        # Kiriman ganda: isi identik, hanya message_id berbeda (L017/L018).
        sidik = hashlib.sha1(
            "|".join([r["channel"], r["name"], r["phone"], r["email"],
                      r["message"]]).encode()).hexdigest()[:16]
        r["_sidik"] = sidik
        per_isi[sidik].append(i)

    bentrok: list[dict] = []

    def sambung(indeks: list[int], jenis: str, nilai: str) -> None:
        if len(indeks) < 2:
            return
        # Semua pasangan diperiksa namanya, bukan hanya berurutan.
        for x in range(len(indeks)):
            for y in range(x + 1, len(indeks)):
                i, j = indeks[x], indeks[y]
                if nama_cocok(rows[i]["name"], rows[j]["name"]):
                    g.satukan(i, j)
                else:
                    bentrok.append({
                        "jenis": jenis, "nilai": nilai,
                        "baris_a": rows[i]["row_id"], "nama_a": rows[i]["name"],
                        "baris_b": rows[j]["row_id"], "nama_b": rows[j]["name"],
                        "sebab": (f"{jenis} sama tetapi nama tidak cocok — "
                                  "kemungkinan kontak kantor dipakai bersama"),
                    })

    for nilai, idx in per_telp.items():
        sambung(idx, "nomor", nilai)
    for nilai, idx in per_surel.items():
        sambung(idx, "email", nilai)
    # Isi identik = kiriman ganda, bukan dua orang. Tidak perlu cek nama.
    for nilai, idx in per_isi.items():
        if len(idx) > 1:
            for k in idx[1:]:
                g.satukan(idx[0], k)

    kelompok: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        kelompok[g.cari(i)].append(i)

    identitas = []
    for akar, idx in sorted(kelompok.items(), key=lambda kv: rows[kv[1][0]]["row_id"]):
        anggota = [rows[i] for i in sorted(idx, key=lambda i: rows[i]["received_at"])]
        utama = anggota[0]
        identitas.append({
            "id": f"SAB-{len(identitas) + 1:03d}",
            "nama": utama["name"],
            "nama_varian": sorted({a["name"] for a in anggota}),
            "telp": next((a["_telp"] for a in anggota if a["_telp"]), ""),
            "surel": next((a["_surel"] for a in anggota if a["_surel"]), ""),
            "perusahaan": next((a["company"] for a in anggota if a["company"]), ""),
            "kanal": [a["channel"] for a in anggota],
            "baris": [a["row_id"] for a in anggota],
            "pesan": [a["message"] for a in anggota],
            "pesan_pertama": utama["message"],
            "waktu_pertama": utama["received_at"],
            "_anggota": anggota,
        })

    stat = {
        "baris_masuk": n,
        "identitas": len(identitas),
        "digabung": n - len(identitas),
        "kontak_dipakai_bersama": len(bentrok),
    }

    # Kemungkinan duplikat yang HANYA bisa dikenali dari nama.
    #
    # L022 masuk lewat email, L023 lewat WhatsApp. Keduanya "Fajar Nugroho",
    # tapi tidak berbagi nomor maupun email: yang satu hanya punya email,
    # yang lain hanya punya nomor. Satu-satunya bukti adalah namanya.
    #
    # Sistem ini tidak menggabung atas dasar nama saja — itu aturan yang sama
    # dengan demo, dan alasannya sama: dua orang bisa bernama persis sama.
    # Jadi pasangan seperti ini masuk antrean manusia, bukan digabung.
    #
    # Syaratnya ketat supaya tidak jadi kebisingan: nama harus PERSIS sama
    # (semua kata), minimal dua kata, dan tidak ada kontak yang bertentangan.
    per_nama: dict[tuple, list[int]] = defaultdict(list)
    for i, r in enumerate(rows):
        tok = tuple(nama_bersih(r["name"]))
        if len(tok) >= 2:
            per_nama[tok].append(i)

    mungkin = []
    for tok, idx in per_nama.items():
        if len(idx) < 2:
            continue
        for x in range(len(idx)):
            for y in range(x + 1, len(idx)):
                i, j = idx[x], idx[y]
                if g.cari(i) == g.cari(j):
                    continue          # sudah satu identitas lewat kontak
                mungkin.append({
                    "nama": " ".join(tok),
                    "baris_a": rows[i]["row_id"], "baris_b": rows[j]["row_id"],
                    "sebab": ("nama persis sama tetapi tidak ada nomor/email "
                              "yang sama — tidak digabung, menunggu manusia"),
                })

    stat["kemungkinan_duplikat_nama"] = len(mungkin)
    return identitas, bentrok, stat, mungkin


# ---------------------------------------------------------------------------
# 3. Klasifikasi: bahasa, opt-out, spam
# ---------------------------------------------------------------------------

KATA_ID = {"kami", "saya", "mau", "tanya", "butuh", "bisa", "jasa", "iklan",
           "untuk", "yang", "ini", "sudah", "belum", "harga", "pasang",
           "minta", "bantu", "dengan", "apakah", "dari", "kapan", "kak",
           "toko", "perusahaan", "bikin", "kirim", "info", "halo", "dan",
           "cuma", "jual", "murah", "kelola", "jadwal", "penawaran", "isi",
           "tadi", "besok", "tahun", "berapa", "boleh"}
KATA_EN = {"we", "our", "you", "your", "what", "does", "looking", "for",
           "services", "interested", "hi", "hello", "want", "expand",
           "follow", "include", "rates", "offer", "agencies", "more",
           "details", "about", "sending", "partner", "package", "sales",
           "submission", "week", "discussed", "outbound", "into", "an"}
KATA_DE = {"wir", "sie", "ihr", "ihre", "ihren", "uns", "eine", "einen",
           "für", "können", "guten", "tag", "bitte", "keine", "weiteren",
           "interesse", "an", "ihren", "leistungen", "schicken", "suchen",
           "agentur", "südostasien", "angebot", "diese", "adresse", "emails"}

OPTOUT_ID = [r"\bberhenti\b", r"\bstop\b", r"\bjangan (kirim|hubungi|email)\b",
             r"\bunsubscribe\b", r"\bhapus (saya|data)\b"]
OPTOUT_EN = [r"\bunsubscribe\b", r"\bstop\b", r"\bremove me\b",
             r"\bdo(n'?t| not) contact\b", r"\bopt out\b"]
OPTOUT_DE = [r"\bkeine weiteren e-?mails?\b", r"\babmelden\b", r"\baustragen\b",
             r"\bl[öo]schen sie\b", r"\bnicht mehr\b"]

SPAM = [r"\bjual followers\b", r"\bfollowers (murah|cepat)\b",
        r"\blikes murah\b", r"\b10rb followers\b", r"\bjasa followers\b",
        r"\bpromo followers\b"]


def bahasa(teks: str) -> tuple[str, dict]:
    """Bahasa dari ISI pesan, bukan dari kanal atau nama.

    Klaus Weber (L026) berbahasa Jerman dari namanya, tapi menulis dalam
    bahasa Inggris — yang menentukan adalah tulisannya. Andreas Müller
    (L007) menulis bahasa Jerman dengan nomor +49.
    """
    t = (teks or "").lower()
    kata = set(re.findall(r"[a-zäöüß]+", t))
    skor = {"ID": len(kata & KATA_ID), "EN": len(kata & KATA_EN),
            "DE": len(kata & KATA_DE)}
    terbaik = max(skor, key=lambda k: skor[k])
    if skor[terbaik] == 0:
        return "??", skor          # tidak dikenali -> serahkan ke manusia
    return terbaik, skor


def opt_out(teks: str, bhs: str) -> bool:
    t = (teks or "").lower()
    pola = {"ID": OPTOUT_ID, "EN": OPTOUT_EN, "DE": OPTOUT_DE}.get(bhs, [])
    pola = pola + OPTOUT_ID + OPTOUT_EN + OPTOUT_DE   # periksa semua bahasa
    return any(re.search(p, t) for p in pola)


def spam(teks: str) -> bool:
    t = (teks or "").lower()
    return any(re.search(p, t) for p in SPAM)


# ---------------------------------------------------------------------------
# 5. Pengiriman: retry + DLQ + alarm + handoff
# ---------------------------------------------------------------------------

def _acak(kunci: str, garam: str) -> float:
    """Angka 0..1 yang tetap sama tiap kali dijalankan.

    Kegagalan pengiriman disimulasikan karena kami tidak mengirim pesan
    sungguhan ke 50 lead sintetis. Yang nyata adalah penanganannya: percobaan
    ulang, DLQ, alarm, dan pemutaran ulang.

    Memakai FNV-1a 32-bit, bukan hash pustaka, supaya implementasi JavaScript
    di workflow n8n bisa menghitung angka yang PERSIS sama. Dengan begitu
    "Python dan n8n menghasilkan hal yang sama" bisa diperiksa, bukan hanya
    diklaim. Seeding dari isi membuat daftar kegagalan dapat diulang tetapi
    tidak dapat ditebak dari nomor baris.
    """
    h = 2166136261
    for b in f"{kunci}|{garam}".encode("utf-8"):
        h ^= b
        h = (h * 16777619) & 0xFFFFFFFF
    return h / 4294967296


PERCOBAAN_MAKS = 3
# Satu kategori kegagalan: kanal menolak. Ketiga percobaan gagal, sama seperti
# di workflow n8n — di sana retryOnFail mengulang seluruh node tiga kali dan
# ketiganya gagal juga. Tidak ada kategori "gagal sementara", karena n8n tidak
# menyimpan keadaan antar-percobaan: tulisan $getWorkflowStaticData dari node
# yang melempar error dibuang. Memodelkan dua kategori akan membuat angka
# Python dan n8n berbeda, dan itu sudah terbukti saat diuji.
P_GAGAL = 0.16         # kanal menolak di semua percobaan -> DLQ
# Ambang alarm: berapa antrean gagal yang dianggap perlu membangunkan orang.
# Lima dipilih karena di bawah itu biasanya reda sendiri dalam satu putaran
# ulang; di atas itu berarti ada kanal yang benar-benar bermasalah.
AMBANG_ALARM = 5


def tujuan_bisa_dipakai(ident: dict) -> tuple[bool, str]:
    """Apakah identitas ini punya saluran yang benar-benar bisa dibalas?

    Balasan dikirim di kanal tempat ia masuk. Formulir butuh email; WhatsApp
    butuh nomor. Tanpa itu, balasan tidak mungkin sampai.
    """
    kanal = ident["kanal"][-1]
    if kanal == "whatsapp":
        return (bool(ident["telp"]), "nomor")
    return (bool(ident["surel"]), "email")


def kirim(identitas: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """Kirim balasan pertama. Kembalikan (terkirim, dlq, jejak_percobaan)."""
    terkirim, dlq, jejak = [], [], []
    for ident in identitas:
        if ident["_dikecualikan"]:
            continue
        bisa, jalur = tujuan_bisa_dipakai(ident)
        if not bisa:
            dlq.append({
                "id": f"DLQ-{len(dlq) + 1:03d}",
                "identitas": ident["id"],
                "nama": ident["nama"],
                "kanal": ident["kanal"][-1],
                "percobaan": 0,
                "error_message": f"tidak ada {jalur} untuk membalas",
                "original_payload": {"pesan": ident["pesan_pertama"]},
            })
            continue

        kunci = f"{ident['id']}|{jalur}"
        gagal = _acak(kunci, "permanen") < P_GAGAL

        catatan = []
        berhasil = False
        for percobaan in range(1, PERCOBAAN_MAKS + 1):
            gagal_kini = gagal
            catatan.append({"percobaan": percobaan,
                            "hasil": "gagal" if gagal_kini else "terkirim"})
            if not gagal_kini:
                berhasil = True
                break
        jejak.append({"identitas": ident["id"], "percobaan": catatan})

        if berhasil:
            terkirim.append({"identitas": ident["id"], "nama": ident["nama"],
                             "kanal": ident["kanal"][-1], "bahasa": ident["bahasa"],
                             "percobaan_ke": percobaan})
        else:
            dlq.append({
                "id": f"DLQ-{len(dlq) + 1:03d}",
                "identitas": ident["id"],
                "nama": ident["nama"],
                "kanal": ident["kanal"][-1],
                "percobaan": PERCOBAAN_MAKS,
                "error_message": "kanal menolak setelah 3 percobaan (5xx)",
                "original_payload": {"pesan": ident["pesan_pertama"]},
            })
    return terkirim, dlq, jejak


def putar_ulang(dlq: list[dict]) -> tuple[list[dict], list[dict]]:
    """Putar ulang isi DLQ setelah penyebabnya diperbaiki.

    Yang gagal karena tidak punya saluran TIDAK ikut diputar: itu bukan
    kegagalan sementara, itu data yang memang kurang. Yang diputar hanya
    kegagalan pengiriman, dan sebagian berhasil.
    """
    pulih, sisa = [], []
    for item in dlq:
        if "tidak ada" in item["error_message"]:
            sisa.append(item)
            continue
        if _acak(f"{item['identitas']}|putar", "ulang") < 0.55:
            pulih.append(item)
        else:
            sisa.append(item)
    return pulih, sisa


# ---------------------------------------------------------------------------
# 6. Rekonsiliasi
# ---------------------------------------------------------------------------

def rekonsiliasi(identitas: list[dict], terkirim: list[dict],
                 dlq: list[dict]) -> dict:
    """Bandingkan yang seharusnya dibalas dengan yang benar-benar dibalas.

    Pengecualian diambil dari isi DLQ, bukan dari rumus indeks. Konsekuensinya:
    daftarnya bergantung pada data dan pada hasil pengiriman, sehingga tidak
    bisa ditebak tanpa menjalankan sistem.
    """
    harus = [i["id"] for i in identitas if not i["_dikecualikan"]]
    dapat = {t["identitas"] for t in terkirim}
    gagal = [d for d in dlq if "tidak ada" not in d["error_message"]]
    tanpa_saluran = [d for d in dlq if "tidak ada" in d["error_message"]]
    return {
        "identitas_total": len(identitas),
        "seharusnya_dibalas": len(harus),
        "benar_benar_dibalas": len(dapat),
        "selisih": len(harus) - len(dapat),
        "pengecualian": sorted(i for i in harus if i not in dapat),
        "sebab_pengecualian": (
            [{"identitas": d["identitas"], "sebab": "pengiriman gagal 3x"}
             for d in gagal]
            + [{"identitas": d["identitas"], "sebab": d["error_message"]}
               for d in tanpa_saluran]
        ),
        "dikecualikan_optout": [i["id"] for i in identitas if i["_optout"]],
        "dikecualikan_spam": [i["id"] for i in identitas if i["_spam"]],
    }


# ---------------------------------------------------------------------------
# Jalankan
# ---------------------------------------------------------------------------

def main() -> int:
    with open(CSV_MASUK, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    identitas, bentrok, stat, mungkin = kelompokkan(rows)

    # Klasifikasi per identitas. Pesan terakhir yang menentukan status terkini:
    # orang yang mengirim "berhenti" pada pesan ketiga sudah opt-out sekarang.
    for ident in identitas:
        semua = ident["pesan"]
        bhs_terakhir, skor = bahasa(semua[-1])
        bhs_pertama, _ = bahasa(semua[0])
        ident["bahasa"] = bhs_terakhir if bhs_terakhir != "??" else bhs_pertama
        ident["skor_bahasa"] = skor
        ident["_optout"] = any(opt_out(p, ident["bahasa"]) for p in semua)
        ident["_spam"] = any(spam(p) for p in semua)
        ident["_dikecualikan"] = ident["_optout"] or ident["_spam"]
        ident["balasan_lintas_kanal"] = len(set(ident["kanal"])) > 1
        ident["kanal_pertama"] = ident["kanal"][0]

    terkirim, dlq, jejak = kirim(identitas)
    # Alarm dibaca SEBELUM pemutaran ulang: itu saat orang perlu dibangunkan.
    alarm_awal = len(dlq) >= AMBANG_ALARM
    pulih, sisa = putar_ulang(dlq)
    alarm_akhir = len(sisa) >= AMBANG_ALARM

    # Yang berhasil diputar ulang benar-benar terkirim, jadi harus ikut
    # dihitung sebagai terkirim. Tanpa ini, rekonsiliasi melaporkan selisih
    # yang sebenarnya sudah tertutup.
    terkirim_semua = terkirim + [
        {"identitas": p["identitas"], "nama": p["nama"], "kanal": p["kanal"],
         "bahasa": next((i["bahasa"] for i in identitas
                         if i["id"] == p["identitas"]), ""),
         "percobaan_ke": 0, "dipulihkan_dari_dlq": True}
        for p in pulih]
    rek = rekonsiliasi(identitas, terkirim_semua, sisa)

    # Handoff ke manusia: yang tidak boleh diputuskan mesin.
    manusia = []
    for ident in identitas:
        alasan = []
        if not nama_bersih(ident["nama"]):
            alasan.append("nama tidak ada / tidak bisa dibaca")
        if ident["bahasa"] == "??":
            alasan.append("bahasa tidak dikenali")
        if any(b["baris_a"] in ident["baris"] or b["baris_b"] in ident["baris"]
               for b in bentrok):
            alasan.append("kontak dipakai bersama — mungkin bukan orang yang sama")
        if alasan:
            manusia.append({"identitas": ident["id"], "nama": ident["nama"],
                            "alasan": alasan})
    for m in mungkin:
        manusia.append({
            "identitas": f"{m['baris_a']}/{m['baris_b']}",
            "nama": m["nama"],
            "alasan": [m["sebab"]],
        })

    alarm = alarm_awal

    hasil = {
        "dijalankan": datetime.now().astimezone().isoformat(timespec="seconds"),
        "sumber": CSV_MASUK.name,
        "poin_1_dedup": {
            **stat,
            "kontak_bersama": bentrok,
            "kemungkinan_duplikat": mungkin,
            "daftar": [{k: v for k, v in i.items()
                        if not k.startswith("_") and k != "_anggota"}
                       for i in identitas],
        },
        "poin_2_bahasa": {
            "sebaran": {b: sum(1 for i in identitas if i["bahasa"] == b)
                        for b in sorted({i["bahasa"] for i in identitas})},
            "per_identitas": {i["id"]: {"bahasa": i["bahasa"],
                                        "kanal_pertama": i["kanal_pertama"]}
                              for i in identitas},
        },
        "poin_3_optout": {
            "opt_out": [{"identitas": i["id"], "nama": i["nama"],
                         "pesan": i["pesan"][-1]}
                        for i in identitas if i["_optout"]],
            "lintas_kanal": [i["id"] for i in identitas
                             if i["balasan_lintas_kanal"]],
        },
        "poin_5_kirim": {
            "terkirim": len(terkirim_semua),
            "dlq_awal": len(dlq),
            "dlq_setelah_putar_ulang": len(sisa),
            "dipulihkan": len(pulih),
            "alarm_kedalaman_dlq_saat_kirim": alarm_awal,
            "alarm_kedalaman_dlq_setelah_putar_ulang": alarm_akhir,
            "ambang_alarm": AMBANG_ALARM,
            "dlq": sisa,
            "jejak_retry": jejak,
            # Bukti percobaan ulang: berapa item yang perlu dicoba lebih dari
            # sekali, dan berapa total percobaan yang dijalankan. Angka ini
            # harus sama dengan yang dilaporkan workflow n8n.
            "item_dicoba_ulang": sum(1 for j in jejak if len(j["percobaan"]) > 1),
            "total_percobaan": sum(len(j["percobaan"]) for j in jejak),
            "handoff_manusia": manusia,
        },
        "poin_6_rekonsiliasi": rek,
        "spam": [{"identitas": i["id"], "nama": i["nama"]}
                 for i in identitas if i["_spam"]],
    }

    (AKAR / "hasil_ujian.json").write_text(
        json.dumps(hasil, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---- ringkasan ke layar + log
    baris = []
    def c(t=""):
        baris.append(t)
        print(t)

    c("=" * 74)
    c("UJIAN 50 LEAD SAB — enam poin")
    c("=" * 74)
    c(f"baris masuk            : {stat['baris_masuk']}")
    c(f"identitas setelah dedup: {stat['identitas']}")
    c(f"digabung               : {stat['digabung']}")
    c(f"kontak dipakai bersama : {stat['kontak_dipakai_bersama']}")
    c(f"kemungkinan duplikat   : {stat['kemungkinan_duplikat_nama']} (nama sama, tanpa kontak bersama)")
    c("")
    c(f"bahasa                 : {hasil['poin_2_bahasa']['sebaran']}")
    c(f"opt-out                : {[x['identitas'] for x in hasil['poin_3_optout']['opt_out']]}")
    c(f"spam                   : {[x['identitas'] for x in hasil['spam']]}")
    c(f"balasan lintas kanal   : {len(hasil['poin_3_optout']['lintas_kanal'])} identitas")
    c("")
    c(f"terkirim               : {len(terkirim_semua)}")
    c(f"DLQ awal               : {len(dlq)}")
    c(f"dipulihkan dari DLQ    : {len(pulih)}")
    c(f"DLQ akhir              : {len(sisa)}")
    c(f"alarm saat kirim       : {'MENYALA' if alarm_awal else 'tidak'} "
      f"(ambang {AMBANG_ALARM}, DLQ {len(dlq)})")
    c(f"alarm setelah putar    : {'MENYALA' if alarm_akhir else 'tidak'} "
      f"(ambang {AMBANG_ALARM}, DLQ {len(sisa)})")
    c(f"handoff manusia        : {len(manusia)}")
    c("")
    c(f"rekonsiliasi           : {rek['benar_benar_dibalas']}/{rek['seharusnya_dibalas']} "
      f"dibalas, selisih {rek['selisih']}")
    c(f"pengecualian           : {', '.join(rek['pengecualian']) or '-'}")
    c("")
    c("Kontak dipakai bersama (tidak digabung):")
    for b in bentrok:
        c(f"  - {b['jenis']} {b['nilai']}: {b['baris_a']} {b['nama_a']!r} "
          f"vs {b['baris_b']} {b['nama_b']!r}")
    c("")
    c("DLQ:")
    for d in sisa:
        c(f"  - {d['id']} {d['identitas']} {d['nama']!r}: {d['error_message']}")
    c("")
    c(f"Hasil: {AKAR / 'hasil_ujian.json'}")

    (AKAR / "log_ujian.txt").write_text("\n".join(baris) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
