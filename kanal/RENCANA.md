# Enam poin Tico: mana yang benar-benar terhalang, mana yang hanya terlihat terhalang

Dokumen ini menjawab satu pertanyaan: dari enam poin di surat 20 November, apa
yang **benar-benar** butuh akun SAB, dan apa yang bisa dikerjakan sekarang
memakai mode uji yang memang disediakan penyedianya.

Kesimpulannya lebih baik daripada yang saya tulis sebelumnya. Saya sempat
mengatakan WhatsApp Business dan form iklan tidak bisa dikerjakan tanpa akun
terverifikasi. Itu salah. Keduanya punya mode uji resmi yang tidak butuh
verifikasi bisnis, dan mode itu cukup untuk seluruh demo.

---

## Ringkasan

| Kanal | Bisa didemokan hari ini? | Yang dibutuhkan untuk produksi | Siapa |
|---|---|---|---|
| Form website | Ya | Tidak ada | Saya |
| Email | Ya | Satu kotak surat + kredensial IMAP/SMTP | Saya |
| WhatsApp | **Ya** — Twilio Sandbox | WhatsApp Business Cloud API milik SAB | Saya, dengan nomor SAB |
| Meta Lead Ads | **Ya** — Lead Ads Testing Tool | Aplikasi Meta + App Review + verifikasi bisnis | Saya, dengan akun SAB |
| Google Lead Form | **Ya** — webhook + payload uji resmi | Akun Google Ads SAB | Saya, dengan akun SAB |
| LinkedIn Lead Gen | Sebagian | Marketing Developer Platform + izin `r_events_leadgen_automation` | SAB, atau lewat konektor pihak ketiga |

Lima dari enam kanal bisa dijalankan sekarang tanpa satu pun akun SAB. Yang
keenam — LinkedIn — memang berpagar, tapi pagarnya bisa dilewati dengan dua cara
yang keduanya tidak menuntut SAB membuka akses API.

---

## Per kanal

### 1. Form website — selesai

Kita yang membuat formnya, jadi kita yang menentukan bentuknya. `kanal/contoh/06`
dan `07` memakai bentuk ini.

Yang perlu diwaspadai: karena bentuknya kita tentukan sendiri, kanal ini juga
paling lemah sebagai bukti. Form yang dibuat sendiri selalu cocok dengan
parser-nya sendiri. Karena itu di `normalkan.py` kanal ini diperlakukan sama
seperti kanal lain — bukan jalur khusus.

### 2. Email — selesai

Dibaca lewat IMAP. Tidak ada format, jadi nama diambil dari header `from` dan
nomor dicari di badan surat termasuk tanda tangan.

Ini kanal yang paling rapuh, dan itu bukan alasan melewatinya. Yang penting:
kalau nomor tidak ditemukan, nomornya dibiarkan kosong dan lead tetap masuk.
Nomor karangan cukup untuk menggabungkan dua orang berbeda, dan itu tidak bisa
ditarik kembali.

### 3. WhatsApp — bisa sekarang, lewat Twilio Sandbox

**Yang saya salah sebutkan sebelumnya:** "butuh nomor bisnis terverifikasi dan
template disetujui Meta". Itu benar untuk produksi, tidak benar untuk demo.

Twilio menyediakan sandbox dengan satu nomor bersama (`+14155238886`). Tidak
perlu WhatsApp Business Account, tidak perlu sender terdaftar. Nomor pengirim
didaftarkan dengan mengirim kode join, lalu pesan masuk dikirim sebagai webhook
ke URL kita.

Bentuk payload-nya sudah ada di `kanal/contoh/01_whatsapp_twilio.json`. Perhatikan
`WaId` — nomor tanpa awalan `+` — dan `ProfileName` yang hanya ada kalau pengirim
mengisi profil WhatsApp-nya. Dua hal itu yang paling sering membuat parser salah.

Untuk produksi: WhatsApp Business Cloud API milik SAB. Ada kuota percakapan
gratis per bulan, dan batas 250 penerima unik per 24 jam sebelum verifikasi bisnis
selesai — cukup untuk berjalan, tidak cukup untuk kampanye besar.

### 4. Meta Lead Ads — bisa sekarang, lewat Lead Ads Testing Tool

Meta punya alat resmi yang membuat lead uji pada form tanpa menjalankan iklan
sama sekali. Artinya seluruh alur bisa diuji ujung ke ujung tanpa membelanjakan
uang iklan dan tanpa App Review.

Bentuk payload-nya di `kanal/contoh/02_meta_lead_ads.json`: `field_data` berupa
array `{name, values}`, dan nama field ditentukan pemilik form. Karena itu
`dari_meta_lead()` memetakan lewat daftar sinonim (`full_name` / `nama_lengkap` /
`name`), bukan lewat posisi.

Untuk produksi: aplikasi Meta milik SAB, App Review, verifikasi bisnis, lalu
berlangganan webhook `leadgen`.

### 5. Google Lead Form — bisa sekarang, lewat webhook resmi

Google mendokumentasikan webhook Lead Form secara terbuka: satu POST ke URL kita,
dengan `user_column_data` berisi `column_id` tetap (`FULL_NAME`, `EMAIL`,
`PHONE_NUMBER`, `COMPANY_NAME`). Ada juga penanda `is_test` dan akun uji Google
Ads yang tidak menagih belanja.

Karena `column_id`-nya tetap dan berbahasa Inggris, kanal ini justru yang paling
stabil diparsing — lebih stabil daripada Meta yang nama field-nya bebas.

Untuk produksi: akun Google Ads SAB, dan pendaftaran URL webhook di aset form.

### 6. LinkedIn — ini yang benar-benar berpagar

Lead Gen Forms butuh izin `r_events_leadgen_automation`, dan izin itu tergolong
terbatas: harus lewat Marketing Developer Platform, dengan peninjauan use case.

Dua jalan yang tidak menuntut SAB membuka API:

1. **Konektor pihak ketiga.** Zapier, Make, dan LeadsBridge sudah memegang izin
   itu di aplikasi mereka. Kita memakai konektor mereka, bukan mendaftarkan
   aplikasi sendiri. Biayanya langganan konektor, bukan waktu peninjauan.
2. **Notifikasi email LinkedIn.** Setiap lead masuk memicu email pemberitahuan.
   Kanal email sudah jalan, jadi ini hanya soal menambah satu pola pengurai.
   Lebih rapuh, tapi tidak butuh izin apa pun.

Saya sarankan nomor 1 untuk produksi dan nomor 2 sebagai jaring pengaman, karena
nomor 2 tidak bergantung pada persetujuan siapa pun.

---

## Yang sudah diuji, bukan direncanakan

`kanal/uji_kanal.py` menjalankan tujuh payload dari enam kanal melalui
normalisasi yang sama, lalu melalui mesin dedup yang sama:

```
6 kanal -> 1 pipeline, 7 baris -> 5 identitas, 0 salah gabung.
LULUS: 19/19 uji kanal
```

Dua hal yang paling mudah salah, dan keduanya diuji:

- **Budi** datang dari WhatsApp (K01, nomor `6281200001101`, tanpa email) lalu
  dari form website (K06, nomor `0812-0000-1101`, dengan email). Digabung.
- **Maria** dari LinkedIn dan **Joko** dari form website memakai email kantor
  yang sama, `info@sinarabadi.example`. **Tidak** digabung, dan pasangannya
  masuk antrean manusia.

Yang kedua itu penting: penggabungan lewat email kantor adalah cara tercepat
untuk mencampur riwayat percakapan dua orang, dan tidak ada cara memisahkannya
setelah terjadi.

Idempotensi juga diuji pada kunci asli dari kanalnya, bukan kunci buatan:
`MessageSid` dari Twilio, `lead_id` dari Google, `message-id` dari email.
Tujuh baris dikirim dua kali menjadi tujuh, bukan empat belas.

---

## Sisa enam poin, apa adanya

| Poin | Keadaan | Yang tersisa |
|---|---|---|
| 1. Lima kanal, dedup lintas kanal | Adaptor 6 kanal berjalan dan teruji | Sambungan ke akun asli (sandbox dulu) |
| 2. Kualifikasi + balasan ≤5 menit, ID/EN/DE | Belum dibangun | Mesin balasan + antrean bahasa. Bisa dikerjakan tanpa akun apa pun |
| 3. Berhenti lintas kanal, opt-out ≤1 menit | Logika sudah ada di mesin ujian | Tabel penekanan bersama + pemeriksaan sebelum kirim |
| 4. Sinkron dua arah CRM | Berjalan, 41 uji + 55 nilai lewat HTTP | Nama field CRM SAB |
| 5. Idempotensi, retry, DLQ, handoff | Berjalan, log eksekusi n8n nyata | Sambungan ke kanal asli |
| 6. Rekonsiliasi harian | Berjalan | Tidak ada |

Jadi dari enam poin, empat sudah punya kode yang berjalan, satu (poin 2) belum
dibangun tapi tidak butuh akun siapa pun, dan satu (poin 3) tinggal disatukan.

Yang benar-benar menunggu SAB hanya tiga hal, dan tidak satu pun di antaranya
menghalangi demo:

1. Nama field CRM mereka — atau satu contoh respons JSON.
2. Akun kanal asli, untuk naik dari sandbox ke produksi.
3. Volume lead per bulan, untuk menentukan ukuran server.

---

## Biaya, tanpa angka karangan

| Hal | Perkiraan |
|---|---|
| n8n self-hosted | Gratis (lisensi fair-code) |
| Twilio Sandbox | Kredit percobaan gratis; cukup untuk demo |
| Meta Lead Ads Testing Tool | Gratis |
| Google Ads akun uji | Tidak menagih belanja |
| WhatsApp Cloud API | Ada kuota percakapan gratis per bulan |
| VPS | Berbayar bulanan; ukurannya tergantung volume lead |
| Konektor LinkedIn (kalau dipakai) | Berbayar bulanan |

Saya tidak mencantumkan angka rupiah untuk yang berbayar karena harga ketiga
penyedia itu berubah dan saya tidak mau menuliskan angka yang sudah basi di
dokumen yang dipakai untuk mengambil keputusan. Yang gratis saya sebut gratis
karena memang tidak ada tagihannya.
