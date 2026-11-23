"""Pencocokan identitas lintas kanal untuk demo SAB.

Aturan yang dipakai, dan alasannya:

1. Nomor yang sudah dinormalkan cocok  -> gabung otomatis.
   Nomor adalah satu-satunya field yang tidak berubah bentuknya karena salah ketik
   nama. Kalau nomornya sama, orangnya sama, kecuali nomor kantor dipakai bersama.

2. Email yang sudah dinormalkan cocok  -> gabung otomatis.
   `budi+ads@gmail.com` dan `budi@gmail.com` adalah satu kotak surat.

3. Nama mirip + perusahaan mirip       -> antrean manusia, bukan gabung otomatis.
   Dua orang bernama "Budi Santoso" di PT Sinar Jaya masih mungkin dua orang.

4. Nama mirip + kota sama              -> antrean manusia.

5. Sisanya                             -> biarkan terpisah.
   Salah menggabung lebih mahal daripada salah memisah: lead yang terpisah masih
   bisa digabung belakangan, tapi lead yang sudah tergabung lalu dikirimi pesan
   atas nama orang lain tidak bisa ditarik kembali.

Tanpa dependensi luar.
"""
from __future__ import annotations

import re
import unicodedata

GELAR = {"pak", "bu", "ibu", "bapak", "mr", "mrs", "ms", "dr", "ir", "prof"}


def _huruf(t: str) -> str:
    """Buang aksen: Müller -> Muller, supaya perbandingan tidak meleset."""
    t = unicodedata.normalize("NFKD", t)
    return "".join(c for c in t if not unicodedata.combining(c))


def nomor(n: str) -> str:
    digit = "".join(c for c in (n or "") if c.isdigit())
    if not digit:
        return ""
    if digit.startswith("62"):
        return digit
    if digit.startswith("0"):
        return "62" + digit[1:]
    if digit.startswith("8"):
        return "62" + digit
    return digit


def email(e: str) -> str:
    e = (e or "").strip().lower()
    if "@" not in e:
        return ""
    lokal, domain = e.rsplit("@", 1)
    lokal = lokal.split("+", 1)[0]           # buang +ads, +web
    if domain in ("gmail.com", "googlemail.com"):
        lokal = lokal.replace(".", "")       # gmail mengabaikan titik
    return f"{lokal}@{domain}"


def nama(n: str) -> list[str]:
    n = _huruf((n or "").lower())
    n = re.sub(r"[^a-z\s.]", " ", n)
    bagian = [b for b in n.replace(".", " ").split() if b and b not in GELAR]
    return bagian


def jaro(a: str, b: str) -> float:
    """Jaro similarity, implementasi murni tanpa dependensi."""
    if a == b:
        return 1.0
    la, lb = len(a), len(b)
    if la == 0 or lb == 0:
        return 0.0
    jendela = max(la, lb) // 2 - 1
    cocok_a = [False] * la
    cocok_b = [False] * lb
    cocok = 0
    for i, ch in enumerate(a):
        for j in range(max(0, i - jendela), min(i + jendela + 1, lb)):
            if not cocok_b[j] and b[j] == ch:
                cocok_a[i] = cocok_b[j] = True
                cocok += 1
                break
    if cocok == 0:
        return 0.0
    t = 0
    k = 0
    for i in range(la):
        if cocok_a[i]:
            while not cocok_b[k]:
                k += 1
            if a[i] != b[k]:
                t += 1
            k += 1
    t /= 2
    return (cocok / la + cocok / lb + (cocok - t) / cocok) / 3


def jaro_winkler(a: str, b: str, skala_prefiks: float = 0.1) -> float:
    """Jaro-Winkler: metrik yang lazim dipakai untuk nama orang.

    Memberi bobot lebih pada awalan yang sama, karena "Budi Santoso" dan
    "Budi Santosa" lebih mungkin orang yang sama daripada "Santoso Budi".
    """
    j = jaro(a, b)
    prefiks = 0
    for ca, cb in zip(a, b):
        if ca == cb and prefiks < 4:
            prefiks += 1
        else:
            break
    return round(j + prefiks * skala_prefiks * (1 - j), 4)


def mirip_nama(a: list[str], b: list[str]) -> float:
    """Kemiripan 0..1 untuk nama orang.

    Diambil yang tertinggi dari dua ukuran:
    - Jaro-Winkler pada nama utuh, tahan terhadap salah ketik
    - cakupan token, tahan terhadap urutan terbalik dan nama yang dipendekkan
    """
    if not a or not b:
        return 0.0
    s_jw = jaro_winkler(" ".join(a), " ".join(b))
    set_a, set_b = set(a), set(b)
    irisan = set_a & set_b
    if not irisan:
        return round(s_jw, 3)
    jaccard = len(irisan) / len(set_a | set_b)
    cakupan = len(irisan) / min(len(set_a), len(set_b))
    s_token = 0.4 * jaccard + 0.6 * cakupan
    return round(max(s_jw, s_token), 3)


def mirip_teks(a: str, b: str) -> float:
    ta = set(re.findall(r"[a-z]+", _huruf((a or "").lower())))
    tb = set(re.findall(r"[a-z]+", _huruf((b or "").lower())))
    if not ta or not tb:
        return 0.0
    return round(len(ta & tb) / len(ta | tb), 3)


def sama_nama_lengkap(a: list[str], b: list[str]) -> bool:
    """Benar hanya kalau kedua nama punya minimal dua kata dan kata-katanya sama.

    Nama satu kata tidak pernah cukup untuk menggabung otomatis. "Yusuf" di
    Surabaya dan "Yusuf" yang lain di Surabaya adalah dua orang, dan menggabung
    keduanya berarti mengirim pesan atas nama orang yang salah.
    """
    if len(a) < 2 or len(b) < 2:
        return False
    return set(a) == set(b)


# --------------------------------------------------------------------------
# Blocking — tanpa ini, setiap lead dibandingkan dengan setiap identitas.
# Pada 200 lead itu 20.000 perbandingan; pada 20.000 lead itu 200 juta, dan
# demonya tidak akan selesai dalam waktu yang bisa ditunggu.
# --------------------------------------------------------------------------
STOP_PERUSAHAAN = {"pt", "cv", "tbk", "gmbh", "the", "ud", "koperasi"}


def blok_nama(daftar: list[str]) -> str:
    return daftar[0][:3] if daftar else ""


def blok_perusahaan(p: str) -> str:
    kata = [k for k in re.findall(r"[a-z]+", _huruf((p or "").lower()))
            if k not in STOP_PERUSAHAAN]
    return kata[0][:4] if kata else ""


def kunci_blok(lead: dict) -> set[str]:
    """Kunci pemblokiran: hanya rekaman dengan kunci sama yang perlu dibandingkan."""
    kota = (lead.get("kota") or "").lower()
    kunci: set[str] = set()
    n = blok_nama(nama(lead.get("nama", "")))
    if n:
        kunci.add(f"N:{n}|{kota}")
    p = blok_perusahaan(lead.get("perusahaan", ""))
    if p:
        kunci.add(f"C:{p}|{kota}")
    return kunci


AMBANG_GABUNG = 0.80
AMBANG_ANTREAN = 0.55


def putuskan(lead: dict, kandidat: dict) -> tuple[str, float, str]:
    """Kembalikan (keputusan, skor, alasan).

    keputusan: 'gabung' | 'antrean' | 'pisah'
    """
    n1, n2 = nomor(lead.get("nomor", "")), nomor(kandidat.get("nomor", ""))
    if n1 and n2 and n1 == n2:
        return "gabung", 1.0, "nomor sama setelah dinormalkan"

    e1, e2 = email(lead.get("email", "")), email(kandidat.get("email", ""))
    if e1 and e2 and e1 == e2:
        return "gabung", 0.95, "email sama setelah +tag dan titik dibuang"

    s_nama = mirip_nama(nama(lead.get("nama", "")), nama(kandidat.get("nama", "")))
    s_prsh = mirip_teks(lead.get("perusahaan", ""), kandidat.get("perusahaan", ""))
    kota_sama = (lead.get("kota", "").lower() == kandidat.get("kota", "").lower()
                 and bool(lead.get("kota")))

    skor = 0.55 * s_nama + 0.30 * s_prsh + (0.15 if kota_sama else 0.0)
    skor = round(skor, 3)

    # Jalur nama TIDAK PERNAH menggabung otomatis, sekalipun namanya persis sama.
    # Alasannya ditemukan saat menguji data ini sendiri: dua orang berbeda bisa
    # bernama "Nadia Pratama" di perusahaan yang sama di kota yang sama. Nama
    # hanya boleh mengantar ke antrean manusia, tidak mengambil keputusan.
    #
    # Ambang antrean dibuat ketat. Antrean yang berisi 118 pasangan tidak akan
    # pernah diperiksa manusia, jadi antrean yang terlalu longgar sama saja
    # dengan tidak punya antrean.
    if sama_nama_lengkap(nama(lead.get("nama", "")), nama(kandidat.get("nama", ""))) \
            and s_prsh >= 0.80 and kota_sama:
        return "antrean", max(skor, 0.90), "nama lengkap sama, perusahaan dan kota sama"

    if s_nama >= 0.92:
        return "antrean", max(skor, 0.75), "nama nyaris identik, perlu dilihat manusia"
    if s_nama >= 0.82 and s_prsh >= 0.80 and kota_sama:
        return "antrean", max(skor, 0.70), "nama mirip, perusahaan dan kota sama"
    return "pisah", skor, "tidak cukup bukti"
