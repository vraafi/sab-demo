"""Pencocokan identitas lintas kanal untuk demo SAB.

Aturan yang dipakai, dan alasannya:

1. Nomor yang sudah dinormalkan cocok  -> gabung otomatis.
   Nomor adalah satu-satunya field yang tidak berubah bentuknya karena salah ketik
   nama. Kalau nomornya sama, orangnya sama, kecuali nomor kantor dipakai bersama.

2. Email yang sudah dinormalkan cocok  -> gabung otomatis.
   `budi+ads@gmail.com` dan `budi@gmail.com` adalah satu kotak surat.

3. Sapaan bergender bertentangan       -> PISAH, sebelum skor dihitung.
   "Pak Dewi" dan "Ibu Dewi" adalah dua orang berbeda. Di Indonesia sapaan
   (Pak/Bapak/Mas untuk laki-laki; Bu/Ibu/Mbak untuk perempuan) adalah penanda
   gender, bukan formalitas. Membuangnya lalu mencocokkan sisanya akan
   menggabungkan dua orang yang berbeda gender -- kesalahan yang tidak bisa
   ditarik kembali. Sapaan karena itu TIDAK dibuang; ia dibaca sebagai sinyal
   dan dibandingkan lebih dulu.

4. Nama mirip + perusahaan mirip       -> antrean manusia, bukan gabung otomatis.
   Dua orang bernama "Budi Santoso" di PT Sinar Jaya masih mungkin dua orang.

5. Nama mirip + kota sama              -> antrean manusia.

6. Sisanya                             -> biarkan terpisah.
   Salah menggabung lebih mahal daripada salah memisah: lead yang terpisah masih
   bisa digabung belakangan, tapi lead yang sudah tergabung lalu dikirimi pesan
   atas nama orang lain tidak bisa ditarik kembali.

Catatan revisi 23 Nov 2026 (menanggapi catatan SAB):
- Sapaan bergender tidak lagi dibuang sebagai gelar; lihat aturan 3.
- Kemiripan nama kini memberi bobot 0,65 pada marga, bukan pada nama depan.
  Sebelumnya "Hendra Halim" dan "Hendra Fischer" bernilai 0,856 hanya karena
  nama depannya sama.
- `sama_nama_lengkap` mensyaratkan marga sama, bukan sekadar himpunan kata sama.

Tanpa dependensi luar.
"""
from __future__ import annotations

import re
import unicodedata

# Gelar yang memang tidak menandakan gender, aman dibuang sebelum mencocokkan.
GELAR_NETRAL = {"dr", "drg", "ir", "prof", "drs", "dra", "st"}

# Sapaan yang menandakan gender. TIDAK dibuang -- dibaca sebagai sinyal.
SAPAAN_L = {"pak", "bapak", "mas", "mr", "h", "haji", "tuan"}
SAPAAN_P = {"bu", "ibu", "mbak", "mrs", "ms", "hj", "hajah", "nyonya", "nona"}

# Gabungan, dipakai untuk membuang sapaan dari token nama supaya blocking tetap
# bekerja pada nama intinya. Gendernya sudah dibaca lebih dulu oleh gender().
SAPAAN = SAPAAN_L | SAPAAN_P


def _huruf(t: str) -> str:
    """Buang aksen: Müller -> Muller, supaya perbandingan tidak meleset."""
    t = unicodedata.normalize("NFKD", t)
    return "".join(c for c in t if not unicodedata.combining(c))


def _token_kasar(n: str) -> list[str]:
    """Token apa adanya, sebelum gelar dan sapaan dibuang."""
    n = _huruf((n or "").lower())
    n = re.sub(r"[^a-z\s.]", " ", n)
    return [b for b in n.replace(".", " ").split() if b]


def gender(n: str) -> str | None:
    """'L' kalau nama menyapa laki-laki, 'P' kalau perempuan, None kalau tidak ada.

    Kalau satu nama memuat sapaan berlawanan (data kotor), hasilnya None:
    lebih baik tidak menyimpulkan apa-apa daripada menyimpulkan salah.
    """
    t = set(_token_kasar(n))
    laki = bool(t & SAPAAN_L)
    perempuan = bool(t & SAPAAN_P)
    if laki and not perempuan:
        return "L"
    if perempuan and not laki:
        return "P"
    return None


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
    """Token nama inti: gelar netral dan sapaan dibuang.

    Sapaan dibuang dari token karena gendernya sudah dibaca terpisah oleh
    gender(); menyisakannya di sini akan mengacaukan pencocokan nama.
    """
    return [b for b in _token_kasar(n)
            if b not in GELAR_NETRAL and b not in SAPAAN]


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


# Bobot marga. Nama depan sangat umum dan berulang; marga yang membedakan orang.
BOBOT_MARGA = 0.65
BOBOT_DEPAN = 0.35


def _mirip_token(x: str, y: str) -> float:
    """Kemiripan satu token nama, dengan perlakuan khusus untuk inisial.

    "Budi S." dan "Budi Santoso" adalah orang yang sama, tapi Jaro-Winkler
    memberi nilai rendah karena "s" dan "santoso" panjangnya jauh berbeda.
    Inisial yang hurufnya cocok karena itu diberi 0,90, bukan dihitung sebagai
    salah ketik.
    """
    if x == y:
        return 1.0
    if len(x) == 1 or len(y) == 1:
        return 0.90 if x[:1] == y[:1] else 0.0
    return jaro_winkler(x, y)


def mirip_nama(a: list[str], b: list[str]) -> float:
    """Kemiripan 0..1 untuk nama orang, dengan marga diberi bobot lebih besar.

    Nama depan saja tidak cukup. "Hendra Halim" dan "Hendra Fischer" berbagi
    nama depan tapi marganya berbeda total -- itu dua orang. Versi sebelumnya
    memberi 0,856 untuk pasangan itu karena menghitung cakupan token, sehingga
    nama depan yang sama menyumbang terlalu banyak.
    """
    if not a or not b:
        return 0.0

    # Nama yang sama persis tapi urutannya tertukar ("Santoso Budi") adalah
    # variasi penulisan yang lazim di formulir, bukan dua orang.
    if len(a) >= 2 and len(b) >= 2 and set(a) == set(b):
        return 1.0

    if len(a) >= 2 and len(b) >= 2:
        depan = _mirip_token(a[0], b[0])
        marga = _mirip_token(a[-1], b[-1])
        skor = BOBOT_DEPAN * depan + BOBOT_MARGA * marga
        # Nama tengah yang sama menambah keyakinan, tapi tidak boleh menutupi
        # marga yang berbeda.
        if len(a) >= 3 and len(b) >= 3:
            tengah = jaro_winkler(" ".join(a[1:-1]), " ".join(b[1:-1]))
            skor = min(1.0, skor + 0.05 * tengah)
        return round(skor, 3)

    # Salah satu nama hanya satu kata: tidak ada marga untuk dibandingkan.
    # Nama depan yang sama terlalu umum, jadi skornya ditahan di 0,85 -- cukup
    # untuk masuk antrean manusia, tidak cukup untuk menggabung otomatis.
    pendek, panjang = (a, b) if len(a) <= len(b) else (b, a)
    cocok = max((_mirip_token(pendek[0], t) for t in panjang), default=0.0)
    return round(min(cocok, 1.0) * 0.85, 3)


def mirip_marga(a: list[str], b: list[str]) -> float:
    """Kemiripan marga saja (kata terakhir). 0,0 kalau salah satu nama satu kata.

    Dipakai sebagai syarat tambahan sebelum masuk antrean. Skor nama gabungan
    bisa tinggi hanya karena nama depannya sama, sehingga "Thomas Weber" dan
    "Thomas Becker" lolos ambang 0,82 padahal marganya berbeda jelas. Marga
    harus cocok sendiri, bukan sekadar menumpang nama depan.
    """
    if len(a) < 2 or len(b) < 2:
        return 0.0
    return _mirip_token(a[-1], b[-1])


def mirip_teks(a: str, b: str) -> float:
    ta = set(re.findall(r"[a-z]+", _huruf((a or "").lower())))
    tb = set(re.findall(r"[a-z]+", _huruf((b or "").lower())))
    if not ta or not tb:
        return 0.0
    return round(len(ta & tb) / len(ta | tb), 3)


def sama_nama_lengkap(a: list[str], b: list[str]) -> bool:
    """Benar hanya kalau kedua nama punya minimal dua kata dan marganya sama.

    Nama satu kata tidak pernah cukup untuk menggabung otomatis. "Yusuf" di
    Surabaya dan "Yusuf" yang lain di Surabaya adalah dua orang, dan menggabung
    keduanya berarti mengirim pesan atas nama orang yang salah.

    Syarat marga ditambahkan 23 Nov: himpunan kata yang sama saja terlalu longgar,
    karena "Hendra Halim" dan "Halim Hendra" berbeda urutan tapi juga bisa dua
    orang. Marga (kata terakhir) harus benar-benar sama.
    """
    if len(a) < 2 or len(b) < 2:
        return False
    return a[-1] == b[-1] and set(a) == set(b)


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

    # Aturan 3: sapaan bergender yang bertentangan berarti dua orang berbeda.
    # Diperiksa sebelum skor dihitung, dan hanya kalau nomor/email tidak cocok.
    g1, g2 = gender(lead.get("nama", "")), gender(kandidat.get("nama", ""))
    if g1 and g2 and g1 != g2:
        nama1, nama2 = lead.get("nama", ""), kandidat.get("nama", "")
        return ("pisah", 0.0,
                f"sapaan berbeda ({nama1!r} vs {nama2!r}): dua orang berbeda gender")

    na, nb = nama(lead.get("nama", "")), nama(kandidat.get("nama", ""))
    s_nama = mirip_nama(na, nb)
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
    # Skor yang dilaporkan untuk jalur ini adalah kekuatan bukti, BUKAN
    # keyakinan sistem. Pasangan dengan skor 1,00 tetap masuk antrean; halaman
    # demo wajib menjelaskan itu, karena tanpa penjelasan angka 1,00 di antrean
    # terbaca seperti kesalahan.
    if sama_nama_lengkap(na, nb) and s_prsh >= 0.80 and kota_sama:
        return "antrean", max(skor, 0.90), "nama lengkap sama, perusahaan dan kota sama"

    if s_nama >= 0.92:
        return "antrean", max(skor, 0.75), "nama nyaris identik, perlu dilihat manusia"

    # Syarat marga hanya berlaku kalau KEDUA nama punya marga. Kalau salah satu
    # nama cuma satu kata ("Lestari"), tidak ada marga untuk dibandingkan, dan
    # memaksakan syarat itu justru membuang kasus yang benar.
    marga_ok = True
    dua_marga = len(na) >= 2 and len(nb) >= 2
    if dua_marga:
        marga_ok = mirip_marga(na, nb) >= 0.85

    if s_nama >= 0.82 and marga_ok and s_prsh >= 0.80 and kota_sama:
        # Kalimat alasan harus jujur: kalau salah satu nama hanya satu kata,
        # tidak ada marga yang dibandingkan, jadi jangan menulis "marga cocok".
        als = ("nama mirip, marga cocok, perusahaan dan kota sama" if dua_marga
               else "nama depan sama (tanpa marga), perusahaan dan kota sama")
        return "antrean", max(skor, 0.70), als
    return "pisah", skor, "tidak cukup bukti"
