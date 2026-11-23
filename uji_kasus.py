"""Uji kasus lapangan untuk dedup SAB.

Data sintetis bisa lolos hanya karena datanya sendiri yang salah. Berkas ini
menguji kasus yang benar-benar muncul di lapangan, terutama yang pernah
dipersoalkan SAB pada 23 Nov 2026, dan yang lazim di Indonesia maupun Jerman.

Setiap kasus menyatakan harapannya. Yang gagal ditampilkan, bukan disembunyikan.

Jalankan: python uji_kasus.py
"""
from __future__ import annotations

import dedup

L = {"nomor": "", "email": "", "perusahaan": "", "kota": ""}


def kasus(nama1, nama2, harap, ket, **beda):
    """Bangun satu kasus.

    Kunci tanpa akhiran "2" berlaku untuk KEDUA lead (perusahaan dan kota yang
    sama). Kunci berakhiran "2" hanya menimpa lead kedua. Versi pertama fungsi
    ini menaruh semua kunci di lead pertama saja, sehingga lead kedua tidak
    punya perusahaan dan kota -- beberapa kasus jadi gagal bukan karena
    logikanya salah, tapi karena datanya tidak lengkap.
    """
    a = {**L, "nama": nama1}
    b = {**L, "nama": nama2}
    for k, v in beda.items():
        if k.endswith("2"):
            b[k[:-1]] = v
        else:
            a[k] = v
            b[k] = v
    return {"a": a, "b": b, "harap": harap, "ket": ket}


KASUS = [
    # --- yang dipersoalkan SAB -------------------------------------------
    kasus("Pak Dewi", "Ibu Dewi", "pisah",
          "sapaan bergender berlawanan = dua orang berbeda",
          kota="München"),
    kasus("Pak Budi Santoso", "Ibu Budi Santoso", "pisah",
          "nama sama tapi Pak vs Ibu: dua orang",
          kota="Bandung"),
    kasus("Mas Agus", "Mbak Agus", "pisah",
          "Mas vs Mbak (Jawa): dua orang",
          kota="Yogyakarta"),
    kasus("Hendra Halim", "Hendra Fischer", "pisah",
          "nama depan sama, marga beda total",
          kota="Jakarta", perusahaan="PT Sinar Jaya"),
    kasus("Rizky Wijaya", "Rizky Wijaya", "antrean",
          "nama lengkap sama: antrean, TIDAK digabung otomatis",
          kota="Jakarta", perusahaan="PT Sinar Jaya"),

    # --- yang HARUS tetap tergabung --------------------------------------
    kasus("Budi Santoso", "Budi Santoso", "gabung",
          "nomor sama ditulis beda format",
          nomor="0812-3456-7890", nomor2="+62 812 3456 7890", kota="Jakarta"),
    kasus("Budi Santoso", "Budi Santoso", "gabung",
          "nomor sama, kurung dan spasi",
          nomor="(0812) 34567890", nomor2="6281234567890", kota="Jakarta"),
    kasus("Budi Santoso", "Budi Santoso", "gabung",
          "email +tag iklan",
          email="budi@gmail.com", email2="budi+ads@gmail.com", kota="Jakarta"),
    kasus("Budi Santoso", "Budi Santoso", "gabung",
          "gmail mengabaikan titik",
          email="budi.santoso@gmail.com", email2="budisantoso@gmail.com",
          kota="Jakarta"),
    kasus("Budi Santoso", "budi santoso", "gabung",
          "huruf besar/kecil",
          nomor="081234567890", nomor2="081234567890", kota="Jakarta"),

    # --- variasi nama yang wajar, harus masuk antrean ---------------------
    kasus("Budi Santoso", "Budi S.", "antrean",
          "marga disingkat: antrean, bukan gabung",
          kota="Bandung", perusahaan="CV Mitra Abadi"),
    kasus("Budi Santoso", "Budi Santosa", "antrean",
          "salah ketik satu huruf di marga",
          kota="Bandung", perusahaan="CV Mitra Abadi"),
    kasus("Budi Santoso", "Santoso Budi", "antrean",
          "urutan nama terbalik",
          kota="Bandung", perusahaan="CV Mitra Abadi"),
    kasus("Dr. Budi Santoso", "Budi Santoso", "antrean",
          "gelar netral (Dr.) dibuang",
          kota="Bandung", perusahaan="CV Mitra Abadi"),
    kasus("Thomas Müller", "Thomas Muller", "antrean",
          "umlaut Jerman dinormalkan",
          kota="München", perusahaan="Nordwind GmbH"),

    # --- yang harus TETAP terpisah ----------------------------------------
    kasus("Budi Santoso", "Budi Hartono", "pisah",
          "nama depan sama, marga beda",
          kota="Bandung", perusahaan="CV Mitra Abadi"),
    kasus("Thomas Weber", "Thomas Becker", "pisah",
          "nama Jerman, marga beda",
          kota="Berlin", perusahaan="Nordwind GmbH"),
    kasus("Yusuf", "Yusuf", "pisah",
          "nama satu kata, beda perusahaan dan kota",
          kota="Surabaya", kota2="Medan",
          perusahaan="Toko Berkah", perusahaan2="Klinik Sehat"),
    kasus("Budi Santoso", "Budi Santoso", "antrean",
          "nama lengkap sama, beda kota/perusahaan: tetap antrean",
          kota="Jakarta", kota2="Medan",
          perusahaan="PT Sinar Jaya", perusahaan2="Hotel Cendana"),
    kasus("Anna Schmidt", "Anna Weber", "pisah",
          "perempuan Jerman, marga beda",
          kota="Berlin", perusahaan="Bäckerei Vogel"),

    # --- lintas kanal: satu punya nomor, satu punya email -----------------
    kasus("Sabine Schmidt", "Sabine Schmidt", "antrean",
          "WhatsApp (nomor saja) vs email (email saja), nama sama",
          kota="Medan", perusahaan="Hotel Cendana",
          nomor="08133328323", nomor2="",
          email="", email2="sabine.schmidt52@gmail.com"),
    kasus("Lestari", "Lestari Becker", "antrean",
          "nama dipendekkan jadi satu kata",
          kota="Berlin", perusahaan="Studio Foto Lensa"),

    # --- kontak kantor dipakai bersama (ditemukan di ujian 50 lead SAB) ---
    # Joko Susilo dan Maria Tan berbagi email dan nomor kantor yang sama.
    # Tanpa penjaga ini, kunci email/nomor menggabung dua orang berbeda --
    # kesalahan yang tidak bisa ditarik kembali. Ditemukan pada L020/L021.
    kasus("Joko Susilo", "Maria Tan", "antrean",
          "email kantor sama, nama tidak cocok: JANGAN digabung",
          kota="Jakarta", perusahaan="PT Sinar Abadi",
          email="info@sinarabadi.example"),

    kasus("Joko Susilo", "Maria Tan", "antrean",
          "nomor kantor sama, nama tidak cocok: JANGAN digabung",
          kota="Jakarta", perusahaan="PT Sinar Abadi",
          nomor="021-5550-0111"),

    # Kendali: kalau namanya memang sama, kunci email tetap boleh menggabung.
    # Tanpa kasus ini, penjaga di atas bisa saja terlalu ketat dan tidak ada
    # yang menyadarinya.
    kasus("Budi Santoso", "Budi Santoso", "gabung",
          "email sama DAN nama sama: gabung otomatis (kendali)",
          kota="Jakarta", perusahaan="PT Sinar Jaya",
          email="budi.santoso@majulogistik.example"),
]


def jalankan() -> int:
    lulus, gagal = 0, []
    for k in KASUS:
        keputusan, skor, alasan = dedup.putuskan(k["a"], k["b"])
        ok = keputusan == k["harap"]
        if ok:
            lulus += 1
        else:
            gagal.append((k, keputusan, skor, alasan))

    print("=" * 72)
    print(f"UJI KASUS LAPANGAN — {len(KASUS)} kasus")
    print("=" * 72)
    for k in KASUS:
        keputusan, skor, _ = dedup.putuskan(k["a"], k["b"])
        tanda = "OK  " if keputusan == k["harap"] else "GAGAL"
        print(f"  {tanda} {k['ket'][:52]:54s}")
        print(f"        {k['a']['nama']!r} vs {k['b']['nama']!r}"
              f" -> {keputusan} ({skor:.3f}), diharap {k['harap']}")

    print(f"\nHASIL: {lulus}/{len(KASUS)} lulus")
    if gagal:
        print(f"\n{len(gagal)} GAGAL:")
        for k, kep, skor, alasan in gagal:
            print(f"  - {k['ket']}")
            print(f"    dapat {kep} ({skor:.3f}), harap {k['harap']} | {alasan}")
        return 1
    print("Semua kasus sesuai harapan.")
    return 0


if __name__ == "__main__":
    raise SystemExit(jalankan())
