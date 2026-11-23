"""Data uji sintetis untuk demo SAB.

Yang dibangkitkan: 200 lead dari 5 kanal, dengan 30 di antaranya adalah orang yang
sama muncul lebih dari sekali dalam bentuk yang tidak konsisten. Ini yang membuat
demo bisa dinilai: kalau dedup-nya asal, angkanya akan kelihatan salah.

Tanpa dependensi luar. Jalankan: python generate.py
"""
from __future__ import annotations

import json
import random
from pathlib import Path

BENIH = 20261120
KANAL = ["form_website", "whatsapp", "email", "google_meta_ads", "linkedin"]

# Nama depan/belakang Indonesia + beberapa Jerman, karena SAB melayani klien Jerman.
DEPAN = ["Budi", "Siti", "Agus", "Dewi", "Rizky", "Putri", "Hendra", "Maya",
         "Fajar", "Indah", "Bayu", "Nadia", "Eko", "Lestari", "Yusuf", "Ayu",
         "Thomas", "Anna", "Michael", "Sabine", "Lukas", "Julia", "Felix", "Clara"]
BELAKANG = ["Santoso", "Wijaya", "Pratama", "Kusuma", "Hidayat", "Nugroho",
            "Saputra", "Halim", "Siregar", "Maulana", "Müller", "Schmidt",
            "Weber", "Fischer", "Becker", "Hoffmann"]
PERUSAHAAN = ["PT Sinar Jaya", "CV Mitra Abadi", "Toko Berkah", "Klinik Sehat",
              "Nordwind GmbH", "Bäckerei Vogel", "PT Karya Logam", "Studio Foto Lensa",
              "CV Rasa Nusantara", "Hotel Cendana"]
KOTA = ["Jakarta", "Bandung", "Surabaya", "Yogyakarta", "Medan", "Berlin", "München"]


def normalkan_nomor(n: str) -> str:
    """Normalkan nomor Indonesia ke bentuk 62xxxxxxxxxx.

    Yang muncul di lapangan: 0812-3456-7890, +62 812 3456 7890, 62812 3456 7890,
    (0812) 34567890, dan 81234567890 tanpa nol di depan.
    """
    digit = "".join(c for c in n if c.isdigit())
    if digit.startswith("62"):
        return digit
    if digit.startswith("0"):
        return "62" + digit[1:]
    if digit.startswith("8"):
        return "62" + digit
    return digit


def variasi_nomor(nomor: str, rng: random.Random) -> str:
    """Tulis ulang satu nomor dalam salah satu format yang biasa dipakai orang."""
    inti = nomor[2:]  # buang '62'
    bentuk = rng.choice([
        "0" + inti,
        "+62" + inti,
        "+62 " + inti[:3] + " " + inti[3:7] + " " + inti[7:],
        "62" + inti,
        "0" + inti[:3] + "-" + inti[3:7] + "-" + inti[7:],
        "(" + "0" + inti[:3] + ") " + inti[3:],
    ])
    return bentuk


def variasi_nama(nama: str, rng: random.Random) -> str:
    bagian = nama.split()
    bentuk = rng.choice([
        nama,
        nama.lower(),
        nama.upper(),
        bagian[0],
        bagian[0] + " " + bagian[-1][0] + ".",
        bagian[0].lower() + " " + bagian[-1].lower(),
        "Pak " + bagian[0],
        "Ibu " + bagian[0],
    ])
    return bentuk


def variasi_email(email: str, rng: random.Random) -> str:
    lokal, domain = email.split("@")
    bentuk = rng.choice([
        email,
        email.upper(),
        lokal + "+" + rng.choice(["ads", "web", "li", "wa"]) + "@" + domain,
        lokal.replace(".", "") + "@" + domain,
        lokal + "@" + domain.lower(),
    ])
    return bentuk


def bangun() -> dict:
    rng = random.Random(BENIH)

    # 170 orang unik, masing-masing punya identitas "benar".
    orang = []
    for i in range(170):
        depan = rng.choice(DEPAN)
        belakang = rng.choice(BELAKANG)
        nama = f"{depan} {belakang}"
        nomor = "62" + rng.choice(["812", "813", "821", "822", "857", "878"]) + \
                "".join(str(rng.randint(0, 9)) for _ in range(7))
        email = f"{depan.lower()}.{belakang.lower().replace('ü', 'u')}{i}@" \
                f"{rng.choice(['gmail.com', 'yahoo.com', 'outlook.com', 'gmx.de'])}"
        orang.append({
            "id": f"P{i:03d}",
            "nama": nama,
            "nomor": nomor,
            "email": email,
            "perusahaan": rng.choice(PERUSAHAAN),
            "kota": rng.choice(KOTA),
        })

    # 200 lead mentah. 170 pertama = satu kemunculan tiap orang.
    # 30 sisanya = 30 orang dari daftar yang sama muncul lagi di kanal lain.
    lead = []
    for o in orang:
        kanal = rng.choice(KANAL)
        lead.append({
            "event_id": f"ev-{len(lead):04d}",
            "kanal": kanal,
            "nama": variasi_nama(o["nama"], rng),
            "nomor": variasi_nomor(o["nomor"], rng) if kanal != "linkedin" else "",
            "email": variasi_email(o["email"], rng) if kanal != "whatsapp" else "",
            "perusahaan": o["perusahaan"],
            "kota": o["kota"],
            "pesan": "Tanya harga dan ketersediaan.",
            "_orang": o["id"],
        })

    duplikat = rng.sample(orang, 30)
    for o in duplikat:
        kanal = rng.choice([k for k in KANAL])
        lead.append({
            "event_id": f"ev-{len(lead):04d}",
            "kanal": kanal,
            "nama": variasi_nama(o["nama"], rng),
            "nomor": variasi_nomor(o["nomor"], rng) if kanal != "linkedin" else "",
            "email": variasi_email(o["email"], rng) if kanal != "whatsapp" else "",
            "perusahaan": o["perusahaan"],
            "kota": o["kota"],
            "pesan": "Follow up dari kanal lain.",
            "_orang": o["id"],
        })

    rng.shuffle(lead)
    return {"orang": orang, "lead": lead}


if __name__ == "__main__":
    data = bangun()
    keluar = Path(__file__).parent / "data_uji.json"
    keluar.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    unik = len({l["_orang"] for l in data["lead"]})
    print(f"lead mentah : {len(data['lead'])}")
    print(f"orang unik  : {unik}")
    print(f"duplikat    : {len(data['lead']) - unik}")
    print(f"disimpan    : {keluar}")
