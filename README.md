# Demo SAB — poin 1, 5, 6

Kode dan hasil uji untuk tiga poin dalam lingkup SAB: dedup lintas kanal,
idempotensi, dan rekonsiliasi harian.

Halaman yang bisa dibaca langsung: **https://vraafi.github.io/sab-demo/**

Repo ini memuat kode yang menghasilkan angka di halaman itu. Tanpa kode, angka
di halaman mana pun hanya klaim — karena itu semuanya ada di sini, termasuk data
ujinya.

## Isi

| Berkas | Untuk apa |
|---|---|
| `dedup.py` | Logika pencocokan identitas: normalisasi nomor/email, kemiripan nama, keputusan gabung/antrean/pisah |
| `demo.py` | Menjalankan uji poin 1, 5, 6 pada `data_uji.json`, menulis `hasil_demo.json` |
| `uji_kasus.py` | 22 kasus lapangan (Indonesia + Jerman) dengan hasil yang diharapkan |
| `uji_kasus_nyata.py` | 12 kasus dari nama orang sungguhan dan konvensi terdokumentasi (Wikipedia), lengkap dengan sumber tiap kasus |
| `uji_kasus_nyata2.py` | 14 kasus putaran kedua: reformasi ejaan 1972, transliterasi Jerman (ß, umlaut), singkatan gelar, dan alias yang benar dipisah |
| `bandingkan.py` | Membandingkan `dedup.py` (baru) dengan `dedup_lama.py` (versi 21 Nov) pada data yang sama |
| `generate.py` | Membangkitkan `data_uji.json` — 170 orang, 200 lead, 30 duplikat |
| `bangun_halaman.py` | Membangun `index.html` dari `hasil_demo.json` |
| `data_uji.json` | Data uji sintetis, termasuk kunci jawaban `_orang` |
| `hasil_demo.json` | Keluaran mentah `demo.py` |
| `log_jalan.txt` | Log eksekusi ketiga skrip di atas |
| `dedup_lama.py` | Versi 21 Nov, disimpan supaya perbandingannya bisa diulang |

## Menjalankan ulang

```bash
python generate.py          # opsional: bangkitkan ulang data uji
python demo.py              # jalankan uji, tulis hasil_demo.json
python uji_kasus.py         # 22 kasus lapangan
python uji_kasus_nyata.py   # 12 kasus nyata dari internet
python uji_kasus_nyata2.py  # 14 kasus nyata putaran kedua
python bandingkan.py        # versi lama vs baru
python bangun_halaman.py    # bangun index.html
```

Tidak ada dependensi luar. Python 3.10+.

## Hasil

```
200 lead -> 173 identitas sementara (170 orang + 3 terpecah)
27 digabung otomatis lewat nomor/email
8 pasangan di antrean manusia (3 orang sama, 5 hanya mirip nama)
0 salah gabung
22/22 kasus lapangan sesuai
12/12 kasus nyata sesuai (10 orang sama, 2 alias benar dipisah)
14/14 kasus nyata putaran kedua sesuai (11 orang sama, 3 alias benar dipisah)
```

## Uji kasus nyata

`uji_kasus_nyata.py` memakai nama tokoh publik dan konvensi yang didokumentasikan
di internet, bukan kasus karangan. Sumbernya dicantumkan per kasus:

- Wikipedia, *Indonesian names* — kategori mononim (Sukarno, Suharto, Boediono),
  marga Batak (Siregar, Nasution), patronimik, dan gelar daerah: Teuku/Cut (Aceh),
  Raden Ajeng (Jawa), Tubagus (Banten), Lalu/Baiq (Sasak), Datuk/Tengku (Melayu).
- Partikel bangsawan Jerman: *von*, *zu*, *von der*, *vom*, *zum* yang mendahului
  marga — relevan karena SAB melayani klien Jerman.
- Transliterasi Jerman ü → ue.

Tiga kasus sempat gagal dan memaksa kode diperbaiki: gelar daerah bergender,
nama panjang yang dipendekkan, dan marga Batak yang sama pada dua orang berbeda.

Dua kasus yang **dipisah** ("Gus Dur" ↔ "Abdurrahman Wahid", "Jokowi" ↔
"Joko Widodo") bukan kegagalan, melainkan perilaku yang diharapkan. Sistem ini
memakai nama asli; nama panggilan tidak boleh disatukan dengan nama asli, karena
menyatukan keduanya adalah kesalahan manusia yang memasukkan julukan ke kolom
nama. Menyatukan nama panggilan, kalau memang perlu, adalah tugas tabel alias
yang diisi manusia — bukan tebakan mesin.

## Uji kasus nyata putaran kedua

`uji_kasus_nyata2.py` menambah 14 kasus dari peristiwa kebahasaan yang
terdokumentasi, bukan dari tebakan. Sumber per kasus ada di berkasnya:

- **Ejaan 1972.** Wikipedia mencatat bahwa pada nama orang ejaan lama justru
  dipertahankan, dan menyebut `Megawati Soekarnoputri` sebagai bentuk baku
  (bukan `Sukarnoputri`). Kasus: Soekarno/Sukarno, Soeharto/Suharto,
  Megawati Soekarnoputri/Sukarnoputri.
- **Transliterasi Jerman.** ß = ss, ü = ue, ö = oe. Kasus: Weiß/Weiss,
  Strauß/Strauss, Jürgen Schröder/Juergen Schroeder.
- **Singkatan gelar.** H. = Haji (laki-laki), Hj. = Hajah (perempuan), dan
  Moh. = Mohammad.
- **Aksen dan partikel.** é, marga ganda bertanda hubung, dan *tussenvoegsel*
  Belanda (van der / van den).
- **Alias yang benar dipisah.** Ganti nama resmi (Ki Hajar Dewantara ↔ Raden Mas
  Soewardi Soerjaningrat), nama Tionghoa diganti nama Indonesia (Liem Sioe Liong
  ↔ Sudono Salim), dan nama panggilan (Joko Widodo ↔ Jokowi).

Dua kasus menemukan cacat nyata di kode:

1. **Huruf ß dibuang, bukan diterjemahkan.** Pembersih karakter hanya menyisakan
   `a-z`, sehingga `Weiß` tersimpan sebagai `wei` — marga Jerman kehilangan
   huruf terakhirnya tanpa peringatan. Sekarang ß → `ss`, dan ø/æ/ł/đ/þ ikut
   dipetakan ke bentuk Latinnya.
2. **Ejaan lama Indonesia tidak dikenali.** `Soekarno` dan `Sukarno` terpisah.
   Sekarang `oe`, `tj`, `dj`, `nj`, `sj`, `ch` dibaca sebagai sinonim tambahan.

Ejaan lama sengaja **tidak** dijadikan normalisasi global: di Jerman `oe` adalah
transliterasi `ö` (Schroeder = Schröder), jadi memetakan `oe` → `u` di seluruh
data akan merusak nama Jerman. Kode mengambil nilai tertinggi dari dua bacaan.

Selain itu, pemisahan nama panggilan kini punya alasan yang dinyatakan.
Sebelumnya `Jokowi` vs `Joko Widodo` terpisah pada skor 0,81 — seperseratus di
bawah ambang, artinya kebetulan, bukan aturan. Sekarang aturannya eksplisit: satu
kata yang tidak muncul di nama yang lebih panjang adalah nama panggilan, dan
sistem memakai nama asli.

**Batas yang jujur:** kedua perbaikan ini tidak mengubah angka pada 200 lead di
atas (173 identitas, 27 digabung, 8 antrean tetap sama), karena generator data uji
tidak pernah menghasilkan ß maupun ejaan 1972. Perbaikan ini dibuktikan oleh kasus
nyata, bukan oleh data demo.

## Yang diperbaiki 23 November 2026

Versi 21 November mendapat empat catatan dari SAB. Semuanya benar:

1. **"Pak Dewi" vs "Ibu Dewi" dinilai nyaris identik.** Penyebabnya sapaan
   dibuang sebagai gelar, sehingga dua orang berbeda gender menyusut jadi satu
   token `['dewi']`. Sekarang sapaan dibaca sebagai sinyal; sapaan berlawanan
   berarti dua orang berbeda dan dipisahkan sebelum skor dihitung.
2. **"Hendra Halim" vs "Hendra Fischer" bernilai 0,921.** Penyebabnya cakupan
   kata, sehingga nama depan yang sama menyumbang terlalu besar. Sekarang marga
   berbobot 0,65 dan nama depan 0,35, dan marga harus cocok sendiri (≥0,85)
   sebelum boleh masuk antrean.
3. **Skor 1,00 muncul di antrean manusia.** Ini bukan bug hitung, melainkan
   keputusan desain yang tidak dijelaskan di halaman. Sekarang halaman
   menjelaskannya: skor adalah kekuatan bukti, bukan izin menggabungkan. Jalur
   nama tidak pernah menggabung otomatis.
4. **27 + 3 = 30, lalu 23 pasangan itu apa.** Angka identitas ditampilkan
   sebagai final padahal antrean belum diputuskan. Sekarang ada tabel
   rekonsiliasi, dan angka 173 ditandai sementara (turun ke 170 setelah antrean
   diputuskan).

Efeknya pada data yang sama: antrean turun dari 23 ke 8 pasangan, **tanpa
kehilangan satu pun duplikat nyata**. Kelima belas pasangan yang keluar
seluruhnya orang berbeda.

## Batas yang diketahui

- **Kanal asli belum disambungkan.** Yang berjalan CRM tiruan dengan data
  sintetis. Pemasangan ke akun SAB adalah pekerjaan tahap 1.
- **Poin 2, 3, 4 belum masuk demo ini.**
- **Generator data masih mengandung satu ketidakkonsistenan:** sapaan Pak/Ibu
  ditulis acak per kemunculan, bukan per orang, sehingga satu orang bisa muncul
  sebagai "Ibu Siti" dan "Pak Siti". Ini tidak mungkin di dunia nyata. Logika
  pencocokan sudah menangani kasusnya dengan benar, tapi datanya perlu
  dibangkitkan ulang agar realistis.
- **Generator tidak menghasilkan ß maupun ejaan 1972.** Karena itu angka pada 200
  lead tidak berubah setelah kedua perbaikan di atas. Kalau data uji dibangkitkan
  ulang dengan variasi ejaan, angkanya akan berubah — dan itu perlu diuji ulang,
  bukan diasumsikan.
