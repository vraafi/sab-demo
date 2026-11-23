"""Uji 14 kasus NYATA, putaran kedua — semuanya diambil dari konvensi dan
peristiwa yang terdokumentasi di internet, bukan dikarang.

Bedanya dengan `uji_kasus_nyata.py`: berkas ini memisahkan dua jenis harapan.

  jenis="cocok"  -> dua penulisan untuk ORANG YANG SAMA.
                    Sistem harus membawa pasangan ini ke antrean manusia.
                    (Tidak pernah menggabung otomatis: bukti nama saja tidak
                    cukup untuk mengambil keputusan.)

  jenis="alias"  -> dua nama untuk orang yang sama, TAPI tidak bisa
                    diselesaikan dengan pencocokan nama (nama panggilan,
                    ganti nama resmi). Sistem harus MEMISAHKANNYA.
                    Memisahkan di sini adalah perilaku yang BENAR, bukan
                    kegagalan: sistem ini memakai nama asli, dan menyatukan
                    nama panggilan dengan nama asli adalah tugas tabel alias
                    yang diisi manusia.

Sumber (semua diakses 23 November 2026):

- Wikipedia bahasa Indonesia, "Ejaan Van Ophuijsen"
  https://id.wikipedia.org/wiki/Ejaan_Van_Ophuijsen
  Mengonfirmasi oe = u, tj = c, dj = j, nj = ny, sj = sy, ch = kh.

- Wikipedia bahasa Indonesia, "Ejaan yang Disempurnakan"
  https://id.wikipedia.org/wiki/Ejaan_yang_Disempurnakan
  Diresmikan 17 Agustus 1972 (Keppres 57/1972). Mengutip langsung:
  "Dalam penggunaannya pada nama, sering kali masih menggunakan ejaan lama,
  misalnya Soekarno ... seperti nama belakang Megawati Soekarnoputri
  (bukan Sukarnoputri maupun Soekarnopoetri)."
  Kutipan ini yang membuat kasus 1-3 bukan karangan: ejaan lama memang
  bertahan pada nama orang Indonesia sampai hari ini.

- Wikipedia, "Indonesian names" — mononim, marga Batak, patronimik, sapaan
  daerah. https://en.wikipedia.org/wiki/Indonesian_names

- Wikipedia bahasa Indonesia, "Haji (gelar)" — H. (Haji) dan Hj. (Hajah).
  https://id.wikipedia.org/wiki/Haji_(gelar)

- Transliterasi Jerman: ß = ss, ü = ue, ö = oe, ä = ae. Lazim dipakai saat
  huruf berdiakritik tidak tersedia (papan ketik, sistem lama, paspor).

- Nama lahir Ki Hajar Dewantara: "Raden Mas Soewardi Soerjaningrat".
  Jurnal Universitas Negeri Yogyakarta,
  https://journal.uny.ac.id/index.php/jpka/article/download/25361/13037

- Liem Sioe Liong / Sudono Salim: berkas otoritas nama (IdRef) mencatat
  "Salim, Sudono", "Salim, Soedono", dan "Liem, Sioe Liong" sebagai varian
  dari satu orang. http://www.idref.fr/183946898

Nomor dan email sengaja kosong: yang diuji adalah perilaku pencocokan nama,
bukan data pribadi siapa pun.

Jalankan: python uji_kasus_nyata2.py
"""
from __future__ import annotations

import dedup

KOSONG = {"nomor": "", "email": "", "perusahaan": "", "kota": ""}


def kasus(nama1, nama2, harap, jenis, ket, sumber, **beda):
    """Susun satu kasus. Kunci berakhiran '2' hanya mengisi pihak B."""
    a = {**KOSONG, "nama": nama1}
    b = {**KOSONG, "nama": nama2}
    for k, v in beda.items():
        if k.endswith("2"):
            b[k[:-1]] = v
        else:
            a[k] = v
            b[k] = v
    return {"a": a, "b": b, "harap": harap, "jenis": jenis,
            "ket": ket, "sumber": sumber}


KASUS = [
    # ---------------------------------------------------------------- ejaan
    # 1. Ejaan 1972: oe -> u. Nama resmi dipertahankan ejaan lamanya, jadi
    #    kedua penulisan ini menunjuk orang yang sama.
    kasus("Soekarno", "Sukarno", "antrean", "cocok",
          "ejaan lama vs baru (oe -> u) pada nama presiden pertama",
          "id.wikipedia EYD: nama sering memakai ejaan lama, mis. Soekarno",
          kota="Jakarta", perusahaan="Istana Negara"),

    # 2. Presiden kedua, pola yang sama.
    kasus("Soeharto", "Suharto", "antrean", "cocok",
          "ejaan lama vs baru (oe -> u) pada nama presiden kedua",
          "id.wikipedia EYD (Keppres 57/1972)",
          kota="Jakarta", perusahaan="Istana Negara"),

    # 3. Ejaan lama bertahan di TENGAH marga majemuk. Wikipedia menyebut
    #    bentuk bakunya "Soekarnoputri", bukan "Sukarnoputri" — jadi variasi
    #    ini benar-benar muncul di data, bukan kemungkinan teoretis.
    kasus("Megawati Soekarnoputri", "Megawati Sukarnoputri", "antrean", "cocok",
          "ejaan lama bertahan di dalam marga majemuk",
          "id.wikipedia EYD: 'Megawati Soekarnoputri (bukan Sukarnoputri)'",
          kota="Jakarta", perusahaan="DPR RI"),

    # 4. Singkatan nama depan yang lazim di dokumen Indonesia.
    kasus("Mohammad Hatta", "Moh. Hatta", "antrean", "cocok",
          "singkatan nama depan (Moh. = Mohammad)",
          "Wikipedia: Mohammad Hatta, lazim ditulis Moh. Hatta",
          kota="Jakarta", perusahaan="Istana Wakil Presiden"),

    # ---------------------------------------------------------------- Jerman
    # 5. ß harus menjadi ss. Sebelum perbaikan, ß dibuang oleh pembersih
    #    karakter sehingga marga "Weiß" menjadi "wei" — nama kehilangan huruf
    #    terakhirnya tanpa peringatan.
    kasus("Michael Weiß", "Michael Weiss", "antrean", "cocok",
          "ß ditulis ss (Weiß -> Weiss)",
          "Transliterasi Jerman: ß = ss",
          kota="München", perusahaan="Südlicht GmbH"),

    # 6. ß di AKHIR marga: kasus yang paling parah kalau ß dibuang.
    kasus("Johann Strauß", "Johann Strauss", "antrean", "cocok",
          "ß di akhir marga (Strauß -> Strauss)",
          "Transliterasi Jerman: ß = ss",
          kota="Wien", perusahaan="Donau Handel GmbH"),

    # 7. Dua transliterasi sekaligus: ü -> ue, ö -> oe.
    kasus("Jürgen Schröder", "Juergen Schroeder", "antrean", "cocok",
          "dua umlaut ditulis dua huruf (ü -> ue, ö -> oe)",
          "Transliterasi Jerman: ü = ue, ö = oe",
          kota="Hamburg", perusahaan="Nordwind GmbH"),

    # ------------------------------------------------------------- gelar ID
    # 8. H. adalah singkatan Haji untuk laki-laki. Keduanya harus terbaca
    #    laki-laki; kalau tidak, aturan gender akan salah memisahkan.
    kasus("H. Ahmad Fauzi", "Haji Ahmad Fauzi", "antrean", "cocok",
          "singkatan gelar haji laki-laki (H. = Haji)",
          "id.wikipedia 'Haji (gelar)': H. = Haji",
          kota="Bandung", perusahaan="PT Priangan Jaya"),

    # 9. Hj. adalah Hajah untuk perempuan. Pasangan ini menguji dua hal
    #    sekaligus: singkatan gelar, dan gender perempuan yang harus konsisten
    #    di kedua sisi (Hj. dan Hajah sama-sama P).
    kasus("Hj. Siti Aminah", "Hajah Siti Aminah", "antrean", "cocok",
          "singkatan gelar haji perempuan (Hj. = Hajah), gender harus konsisten",
          "id.wikipedia 'Haji (gelar)': Hj. = Hajah",
          kota="Surabaya", perusahaan="PT Jawa Timur Sejahtera"),

    # -------------------------------------------------------------- lain-lain
    # 10. Aksen dan tanda hubung pada marga ganda Iberia.
    kasus("Maria José Silva-Santos", "Maria Jose Silva Santos", "antrean", "cocok",
          "aksen (é) dan tanda hubung pada marga ganda",
          "Konvensi nama Iberia: marga ganda dengan tanda hubung",
          kota="Lisboa", perusahaan="Atlântico Lda"),

    # 11. Partikel Belanda (tussenvoegsel) + salah ketik der/den.
    kasus("Jan van der Berg", "Jan van den Berg", "antrean", "cocok",
          "partikel Belanda 'van der' vs 'van den'",
          "Konvensi nama Belanda: tussenvoegsel van/van der/van den",
          kota="Amsterdam", perusahaan="Noordzee BV"),

    # ------------------------------------------------------------------ alias
    # 12. Ganti nama resmi. Dua nama ini menunjuk satu orang, tapi TIDAK ADA
    #     satu kata pun yang sama. Pencocokan nama tidak boleh menebaknya;
    #     memisahkan adalah perilaku benar.
    kasus("Ki Hajar Dewantara", "Raden Mas Soewardi Soerjaningrat", "pisah", "alias",
          "ganti nama resmi — benar dipisah, butuh tabel alias",
          "Jurnal UNY: lahir sebagai Raden Mas Soewardi Soerjaningrat",
          kota="Yogyakarta", perusahaan="Taman Siswa"),

    # 13. Nama Tionghoa diganti nama Indonesia. Berkas otoritas mencatat
    #     keduanya sebagai varian satu orang, tapi sistem tidak boleh menebak.
    kasus("Liem Sioe Liong", "Sudono Salim", "pisah", "alias",
          "nama Tionghoa diganti nama Indonesia — benar dipisah",
          "IdRef: Salim, Sudono / Liem, Sioe Liong (varian satu orang)",
          kota="Jakarta", perusahaan="Salim Group"),

    # 14. Nama panggilan, bukan nama asli. Inilah kasus yang Anda tegaskan:
    #     sistem wajib memakai nama asli, jadi julukan tidak boleh digabung.
    kasus("Joko Widodo", "Jokowi", "pisah", "alias",
          "nama panggilan, bukan nama asli — benar dipisah",
          "Wikipedia: Jokowi adalah nama panggilan Joko Widodo",
          kota="Jakarta", perusahaan="Istana Negara"),
]


def jalankan() -> int:
    print("=" * 78)
    print(f"UJI {len(KASUS)} KASUS NYATA — PUTARAN KEDUA (ejaan, transliterasi, alias)")
    print("=" * 78)

    gagal = []
    for i, k in enumerate(KASUS, 1):
        keputusan, skor, alasan = dedup.putuskan(k["a"], k["b"])
        ok = keputusan == k["harap"]
        if not ok:
            gagal.append((k, keputusan, skor, alasan))
        tanda = "OK   " if ok else "GAGAL"
        label = "cocok" if k["jenis"] == "cocok" else "alias (benar dipisah)"
        print(f"\n{i:2d}. [{tanda}] {k['ket']}")
        print(f"    {k['a']['nama']!r} vs {k['b']['nama']!r}")
        print(f"    dapat: {keputusan} ({skor:.3f}) | harusnya: {k['harap']}  [{label}]")
        print(f"    alasan sistem: {alasan}")
        print(f"    sumber: {k['sumber']}")

    lulus = len(KASUS) - len(gagal)
    n_cocok = sum(1 for k in KASUS if k["jenis"] == "cocok")
    n_alias = len(KASUS) - n_cocok
    print("\n" + "=" * 78)
    print(f"HASIL: {lulus}/{len(KASUS)} sesuai "
          f"({n_cocok} pasangan orang sama, {n_alias} alias yang benar dipisah)")
    if gagal:
        print(f"\n{len(gagal)} TIDAK SESUAI — perlu perbaikan:")
        for k, kep, skor, alasan in gagal:
            print(f"  - {k['ket']}")
            print(f"    dapat {kep} ({skor:.3f}), harusnya {k['harap']} | {alasan}")
        return 1
    print("Semua kasus nyata tertangani dalam satu kali jalan.")
    return 0


if __name__ == "__main__":
    raise SystemExit(jalankan())
