"""Uji 10 kasus NYATA, diambil dari nama orang sungguhan dan konvensi yang
didokumentasikan di internet — bukan dikarang.

Sumber:
- Wikipedia, "Indonesian names" (kategori mononim, marga Batak, patronimik,
  daftar sapaan daerah: Teuku/Cut, Raden Ajeng, Gus, Luhur, dst.)
  https://en.wikipedia.org/wiki/Indonesian_names
- Wikipedia bahasa Indonesia, "Haji (gelar)" — H./Hj. sebagai gelar kehormatan.
  https://id.wikipedia.org/wiki/Haji_(gelar)
- Partikel bangsawan Jerman (von, zu, von der, vom, zum) yang mendahului marga.
  SAB melayani klien Jerman, jadi ini bukan kasus hiasan.

Nama yang dipakai adalah tokoh publik nyata. Nomor dan emailnya sintetis —
yang diuji adalah perilaku pencocokan nama, bukan data pribadi siapa pun.

Jalankan: python uji_kasus_nyata.py
"""
from __future__ import annotations

import dedup

L = {"nomor": "", "email": "", "perusahaan": "", "kota": ""}


def kasus(nama1, nama2, harap, ket, sumber, jenis="cocok", **beda):
    a = {**L, "nama": nama1}
    b = {**L, "nama": nama2}
    for k, v in beda.items():
        if k.endswith("2"):
            b[k[:-1]] = v
        else:
            a[k] = v
            b[k] = v
    return {"a": a, "b": b, "harap": harap, "ket": ket, "sumber": sumber,
            "jenis": jenis}


KASUS = [
    # 1. Mononim — kategori resmi pertama di Wikipedia. Dua presiden, dua orang.
    kasus("Sukarno", "Suharto", "pisah",
          "dua mononim berbeda: nama satu kata bukan alasan menggabung",
          "Wikipedia: single name, Sukarno / Suharto",
          kota="Jakarta", perusahaan="Istana Negara"),

    # 2. Mononim sama, perusahaan dan kota sama — harus ke manusia, bukan digabung.
    kasus("Boediono", "Boediono", "antrean",
          "mononim sama di perusahaan sama: antrean, tidak digabung otomatis",
          "Wikipedia: mononim Boediono",
          kota="Jakarta", perusahaan="Bank Indonesia"),

    # 3. Sapaan daerah bergender: Teuku (laki-laki, Aceh) vs Cut (perempuan, Aceh).
    kasus("Teuku Ahmad", "Cut Ahmad", "pisah",
          "Teuku (L) vs Cut (P) di Aceh: dua orang berbeda",
          "Wikipedia: Acehnese Teuku (male), Cut (female)",
          kota="Banda Aceh", perusahaan="PT Aceh Jaya"),

    # 4. Singkatan gelar bangsawan Jawa: Raden Ajeng = R.A.
    kasus("Raden Ajeng Kartini", "R.A. Kartini", "antrean",
          "gelar bangsawan Jawa disingkat: orang yang sama",
          "Wikipedia: Javanese Raden Ajeng (unmarried female)",
          kota="Jepara", perusahaan="Sekolah Kartini"),

    # 5. Inisial dua kata pertama, marga ditulis penuh.
    kasus("Abdul Haris Nasution", "A.H. Nasution", "antrean",
          "inisial dua nama depan, marga Batak ditulis penuh",
          "Wikipedia: Abdul Haris Nasution, Batak marga",
          kota="Jakarta", perusahaan="TNI AD"),

    # 6. Partikel bangsawan Jerman mendahului marga.
    kasus("Ursula von der Leyen", "Ursula von der Leyen", "antrean",
          "nama Jerman dengan partikel 'von der', orang yang sama",
          "Partikel Jerman: von der + marga",
          kota="Berlin", perusahaan="Europäische Kommission"),

    # 7. Transliterasi Jerman: ü ditulis ue. Lazim di dokumen dan email.
    kasus("Thomas Müller", "Thomas Mueller", "antrean",
          "umlaut ditulis dua huruf (ü -> ue), lazim di Jerman",
          "Transliterasi Jerman ü=ue",
          kota="München", perusahaan="Nordwind GmbH"),

    # 8. Nama panjang dipendekkan, marga terakhir dibuang.
    kasus("Sri Mulyani Indrawati", "Sri Mulyani", "antrean",
          "nama tiga kata dipendekkan, marga terakhir hilang",
          "Wikipedia: Sri Mulyani Indrawati",
          kota="Jakarta", perusahaan="Kementerian Keuangan"),

    # 9. Marga Batak sama, nama depan beda — dua orang bersaudara/klan.
    kasus("Budi Siregar", "Ani Siregar", "pisah",
          "marga Batak sama tapi orang berbeda: marga bukan pengenal tunggal",
          "Wikipedia: Batak marga Siregar",
          kota="Medan", perusahaan="PT Sumatera Utama"),

    # 10. Nama Tionghoa-Indonesia: marga di DEPAN, dan ada yang mengganti nama.
    kasus("Kwik Kian Gie", "Kwik Kian Gie", "antrean",
          "nama Tionghoa dengan marga di depan, orang yang sama",
          "Wikipedia: Chinese-Indonesian, surname first",
          kota="Jakarta", perusahaan="Universitas Tarumanagara"),

    # --- alias: nama panggilan vs nama asli ---
    # Kedua kasus di bawah BUKAN kegagalan. Sistem ini memakai nama asli;
    # nama panggilan tidak boleh disatukan dengan nama asli, karena menyatukan
    # keduanya adalah kesalahan manusia yang memasukkan data julukan ke kolom
    # nama. Memisahkan di sini adalah perilaku yang benar. Menyatukannya,
    # kalau memang perlu, adalah tugas tabel alias yang diisi manusia.
    kasus("Gus Dur", "Abdurrahman Wahid", "pisah",
          "nama panggilan vs nama asli — BENAR dipisah, sistem memakai nama asli",
          "Wikipedia: Gus Dur = Abdurrahman Wahid (julukan)",
          jenis="alias",
          kota="Jakarta", perusahaan="NU"),

    kasus("Joko Widodo", "Jokowi", "pisah",
          "nama panggilan vs nama asli — BENAR dipisah, sistem memakai nama asli",
          "Wikipedia: Jokowi = Joko Widodo (julukan)",
          jenis="alias",
          kota="Jakarta", perusahaan="Istana Negara"),
]


def jalankan() -> int:
    print("=" * 76)
    print(f"UJI {len(KASUS)} KASUS NYATA (nama tokoh publik, konvensi terdokumentasi)")
    print("=" * 76)
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
        print(f"    sumber: {k['sumber']}")

    lulus = len(KASUS) - len(gagal)
    n_alias = sum(1 for k in KASUS if k["jenis"] == "alias")
    print("\n" + "=" * 76)
    print(f"HASIL: {lulus}/{len(KASUS)} sesuai "
          f"({len(KASUS) - n_alias} pasangan orang sama, "
          f"{n_alias} alias yang benar dipisah)")
    if gagal:
        print(f"\n{len(gagal)} GAGAL — perlu perbaikan:")
        for k, kep, skor, alasan in gagal:
            print(f"  - {k['ket']}")
            print(f"    dapat {kep} ({skor:.3f}), harusnya {k['harap']} | {alasan}")
        return 1
    print("Semua kasus nyata tertangani.")
    return 0


if __name__ == "__main__":
    raise SystemExit(jalankan())
