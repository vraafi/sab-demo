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
| `ujian/mesin.py` | Mesin enam poin untuk 50 lead ujian SAB (implementasi rujukan, Python) |
| `ujian/logika.js` | Port JavaScript dari logika yang sama, dipakai di node Code n8n |
| `ujian/workflow_ujian.json` | Workflow n8n untuk 50 lead — dijalankan sungguhan, bukan JSON yang belum pernah dieksekusi |
| `ujian/uji_kesamaan.py` | Membandingkan 24 angka antara mesin Python dan workflow n8n; gagal kalau ada satu perbedaan |
| `ujian/hasil_ujian.json` | Keluaran mesin Python |
| `ujian/hasil_ujian_n8n.json` | Keluaran workflow n8n pada data yang sama |
| `ujian/log_n8n.json` | Ringkasan log eksekusi n8n: semua putaran per node (bukan hanya yang terakhir), termasuk cabang error |
| `poin4/sinkron.py` | Poin 4: sinkron dua arah dengan resolusi konflik per-field, tanpa last-write-wins. Berisi 23 uji |
| `poin4/logika4.js` | Port JavaScript aturan yang sama, dipakai di node Code n8n |
| `poin4/workflow_poin4.json` | Workflow n8n untuk poin 4 — dijalankan sungguhan |
| `poin4/uji_sama.py` | Membandingkan isi tiap field hasil Python dan n8n; gagal kalau ada satu nilai berbeda |
| `poin4/hasil_poin4.json`, `poin4/hasil_poin4_n8n.json` | Keluaran kedua mesin pada data yang sama |
| `poin4/sinkron_api.py` | Poin 4 dijalankan lewat HTTP ke CRM API sungguhan; 55 nilai dibandingkan dengan mesin dalam-proses |
| `crm_api/server.js` | CRM API yang berjalan: auth, ETag/If-Match, Idempotency-Key, kursor delta, tombstone, webhook HMAC, audit. Tanpa dependensi |
| `crm_api/openapi.json` | Spesifikasi OpenAPI 3.1, bisa diimpor ke Postman |
| `crm_api/uji_api.py` | 41 uji integrasi lewat HTTP; keluarannya di `hasil_uji_api.txt` |
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
151 balasan terkirim, 22 gagal 3x masuk DLQ, alarm menyala (ambang 8), 10 sisa
rekonsiliasi 163/173, pengecualian diambil dari DLQ (jarak antar-ID bervariasi)
25/25 kasus lapangan sesuai  (termasuk 3 kasus kontak kantor bersama)
12/12 kasus nyata sesuai (10 orang sama, 2 alias benar dipisah)
14/14 kasus nyata putaran kedua sesuai (11 orang sama, 3 alias benar dipisah)
23/23 uji poin 4 (sinkron dua arah, resolusi konflik per-field)

Ujian 50 lead SAB:
50 baris -> 36 identitas, 14 digabung, 2 kontak dipakai bersama, 1 kemungkinan duplikat
33 seharusnya dibalas, 29 terkirim, 5 DLQ, 1 dipulihkan, 4 sisa
mesin Python vs workflow n8n: 24 angka dibandingkan, 0 perbedaan

Poin 4 lewat HTTP:
41/41 uji integrasi CRM API (auth, idempotensi, ETag, konflik, tombstone, webhook)
27 permintaan HTTP, 4 dijawab 409, 5 konflik terbuka, 1 tombstone
55 nilai dibandingkan dengan mesin dalam-proses, 0 perbedaan
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

## Ujian 50 lead dan workflow n8n

`ujian/` berisi pengerjaan enam poin pada 50 lead sintetis yang dikirim SAB.
Workflow-nya **dijalankan**, bukan hanya dikirim sebagai JSON:

```bash
cd ujian
python mesin.py          # mesin rujukan (Python)  -> hasil_ujian.json
python bangun_workflow.py
n8n import:workflow --input=workflow_ujian.json
n8n execute --id=sabujian001                      -> hasil_ujian_n8n.json
python simpan_log_n8n.py                          -> log_n8n.json
python uji_kesamaan.py                            -> harus 0 perbedaan
```

Node pengiriman memakai mekanisme asli n8n: `retryOnFail` dengan `maxTries: 3`,
`waitBetweenTries: 300`, dan `onError: continueErrorOutput`. Item yang gagal tiga
kali keluar di cabang error dan masuk DLQ. Log eksekusi menunjukkan
`Kirim cabang=[28, 5]` — 28 berhasil, 5 ke DLQ.

Kegagalan pengiriman disimulasikan (tidak ada pesan sungguhan yang dikirim ke 50
lead sintetis), tetapi pembangkitnya FNV-1a atas `id|kanal`, sehingga bisa
dihitung ulang oleh siapa pun dengan kode di repo dan tidak bisa ditebak dari
nomor baris.

### Poin 4 — sinkron dua arah, tanpa last-write-wins

Pemenang ditentukan oleh nenek moyang bersama (nilai terakhir yang disepakati
kedua sisi), bukan oleh `updated_at`. Kalau dua sisi mengubah field yang sama
dengan nilai berbeda, field itu dibiarkan pada nilai dasar dan masuk antrean
konflik; field lain tetap tersinkron. Tidak ada yang menang diam-diam.

```bash
cd poin4
python sinkron.py            # 23 uji, -> hasil_poin4.json + data_poin4.json
python bangun_workflow4.py
n8n import:workflow --input=workflow_poin4.json
n8n execute --id=sabpoin4001 -> hasil_poin4_n8n.json
python simpan_log.py         -> log_n8n.json
python uji_sama.py           -> 91 nilai dibandingkan, harus 0 perbedaan
```

Pada data uji: 9 catatan dasar + 10 lokal + 8 CRM -> 10 catatan hasil gabung,
5 konflik masuk antrean, 1 dihapus. Termasuk kasus hapus-vs-ubah, yang tidak
menghapus apa pun dan menyerahkannya ke manusia.

### CRM API — poin 4 tidak lagi berhenti di dua sisi tiruan

Aturan yang hanya lulus di dalam satu proses belum tentu lulus ketika ada dua
penulis, pengiriman ulang, dan urutan yang tidak dijamin. Karena itu ada server
HTTP sungguhan yang menegakkan janji-janji itu, bukan mengharapkannya dari klien.

```bash
cd crm_api
node server.js                      # port 8787
python uji_api.py                   # 41 uji, -> hasil_uji_api.txt
cd ../poin4 && python sinkron_api.py   # poin 4 lewat HTTP, 55 nilai, harus 0 beda
```

| Rute | Yang ditegakkan |
|---|---|
| `POST /v1/contacts` | Wajib `Idempotency-Key`; kirim ulang tidak membuat kontak kedua |
| `GET /v1/contacts?since=` | Kursor bilangan urut, bukan `updated_at`; tombstone ikut tersebar |
| `PATCH /v1/contacts/{id}` | Per field dengan `base` sebagai nenek moyang bersama; field berkonflik tidak diubah, dijawab `409`, field lain tetap masuk |
| `If-Match` / `ETag` | Tulisan di atas versi basi ditolak `412` |
| `POST /v1/conflicts/resolve` | Satu-satunya jalan keluar konflik, dan hanya manusia |
| `POST /v1/webhooks` | HMAC-SHA256 atas `timestamp.body`, timestamp > 5 menit ditolak, kiriman ganda dikenali |
| `GET /v1/audit` | Siapa mengubah field apa, dari nilai apa ke apa |

Empat keputusan yang diambil dari praktik yang berlaku November 2026:

1. **ETag + If-Match** untuk konkurensi optimistis (Azure Architecture Center,
   *RESTful Web API Implementation Best Practices*). Tanpa ini, dua penulis
   terakhir saling menimpa tanpa ada yang tahu.
2. **Idempotency-Key** untuk POST/PATCH. Pengiriman ulang itu normal, bukan
   kesalahan: webhook bersifat at-least-once dan klien yang timeout akan
   mencoba lagi.
3. **Kursor `seq`, bukan `updated_at`.** Jam dua sistem tidak pernah sama dan
   bisa mundur karena NTP. Alasannya sama dengan alasan poin 4 menolak
   last-write-wins: jam tidak boleh jadi wasit.
4. **HMAC + batas waktu 5 menit.** Tanda tangan saja tidak cukup: tanpa batas
   waktu, satu permintaan sah bisa diputar ulang selamanya.

Yang dibandingkan `sinkron_api.py` bukan "apakah kedua sisi sama", karena pada
field berkonflik keduanya memang harus berbeda. Yang diperiksa: field tanpa
konflik harus identik, field berkonflik di sisi CRM harus tetap memuat nilai CRM
(perubahan orang lain tidak boleh ditimpa), dan catatan gabungan harus tetap
memuat nilai dasar. Kalau ada satu sisi menang diam-diam, uji gagal.

**Jebakan yang berhasil dilewati:** kontak kantor dipakai bersama
(`info@sinarabadi.example` dipakai dua orang berbeda), nama persis sama tanpa
kontak bersama, opt-out dalam bahasa Indonesia dan Jerman, dan domain email salah
ketik (`gmial.example`).

## Tujuh catatan SAB, 23 November 2026

Catatan itu ditulis pukul 09.18; kode masuk repo pukul 11.41–12.07. Tidak ada
catatan yang dibantah — semua benar untuk versi yang diperiksa.

| # | Catatan | Status |
|---|---|---|
| 1 | Repo hanya index.html, skrip tidak ada | Benar saat itu; skrip, data, log sekarang ada |
| 2 | Antrean bertentangan dengan aturan sendiri; ambang/bobot tidak dijelaskan | Diperbaiki: gabung otomatis hanya nomor/email; skor 0,55 nama + 0,30 perusahaan + 0,15 kota; marga ≥0,85 |
| 3 | "Pak Dewi"/"Ibu Dewi" dinilai identik | Diperbaiki: sapaan dibaca sebagai sinyal gender sebelum skor |
| 4 | Angka dedup tidak menutup; 173 dihitung final | Diperbaiki: 170 + 3 = 173, ditandai sementara, antrean 23 → 8 |
| 5 | Poin 5 baru separuh | Diperbaiki: retry 3×, DLQ, alarm kedalaman, pemutaran ulang, handoff |
| 6 | Pengecualian berpola kelipatan 28 | Diperbaiki: `[::28]` dibuang, pengecualian diambil dari isi DLQ |
| 7 | Lingkup n8n, demo Python | Dijawab: produknya n8n (dijalankan, ada log); Python hanya alat ukur, 24 angka identik |

## Batas yang diketahui

- **Kanal asli belum disambungkan.** WhatsApp Business, form website SAB, dan
  email belum tersambung ke akun sungguhan; yang berjalan simulasi kanal di
  dalam workflow. Pemasangan ke akun SAB adalah pekerjaan tahap 1.
- **Poin 4 tersambung ke CRM API rujukan, belum ke CRM SAB.** API-nya berjalan
  dan diuji 41 kali lewat HTTP, tapi nama field dan kredensial CRM SAB belum ada.
- **Volume lead SAB belum diketahui.** Angka itu menentukan kebutuhan server dan
  lama pemrosesan.
- **Generator data masih mengandung satu ketidakkonsistenan:** sapaan Pak/Ibu
  ditulis acak per kemunculan, bukan per orang, sehingga satu orang bisa muncul
  sebagai "Ibu Siti" dan "Pak Siti". Ini tidak mungkin di dunia nyata. Logika
  pencocokan sudah menangani kasusnya dengan benar, tapi datanya perlu
  dibangkitkan ulang agar realistis.
- **Generator tidak menghasilkan ß maupun ejaan 1972.** Karena itu angka pada 200
  lead tidak berubah setelah kedua perbaikan di atas. Kalau data uji dibangkitkan
  ulang dengan variasi ejaan, angkanya akan berubah — dan itu perlu diuji ulang,
  bukan diasumsikan.
