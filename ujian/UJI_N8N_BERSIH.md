# Uji impor di n8n kosong — 24 November 2026

Dijalankan karena satu butir di daftar periksa sebelumnya belum pernah dikerjakan:
`workflow_ujian.json` sudah pernah diimpor dan dijalankan di n8n kerja, tetapi
**belum pernah** di instance kosong. Tanpa uji ini, kalimat "impor satu berkas"
hanya klaim.

## Keadaan awal

Instance baru, basis data baru, tanpa workflow apa pun:

    N8N_USER_FOLDER=tmp/n8n_bersih
    n8n list:workflow        -> (kosong)

Kunci enkripsi dibuat ulang saat start pertama (`No encryption key found -
Auto-generating`), jadi ini benar-benar instance bersih, bukan folder yang sudah
pernah dipakai.

## Langkah dan hasil

**1. Impor**

    n8n import:workflow --input=ujian/workflow_ujian.json
    -> Importing 1 workflows...
    -> Successfully imported 1 workflow.

**2. Jalan pertama — GAGAL**

    n8n execute --id=sabujian001
    -> status: error
    -> Access to the file is not allowed.
       (nodes/Files/ReadWriteFile, operasi read)

Sebabnya bukan workflow-nya. n8n 2.x membatasi node Baca/Tulis Berkas hanya pada
folder yang diizinkan. Di instance kerja pembatas itu sudah terbuka, sehingga
gejalanya tidak pernah muncul. Di instance kosong, node pertama langsung ditolak.

**3. Jalan kedua — BERHASIL**

    N8N_RESTRICT_FILE_ACCESS_TO=<folder proyek> n8n execute --id=sabujian001
    -> status: success
    -> finished: true

Memilih `N8N_RESTRICT_FILE_ACCESS_TO` dan bukan
`N8N_BLOCK_FILE_ACCESS_TO_N8N_FILES=false`: yang pertama **membuka satu folder
tertentu**, yang kedua mematikan pembatasnya sama sekali. Untuk mesin SAB, yang
pertama yang benar.

## Hasil angkanya

Dibandingkan dengan hasil run 23 November di instance kerja: **22 angka, satu
perbedaan** — hanya cap waktu `dijalankan`.

| Ukuran | Nilai |
|---|---|
| Baris masuk | 50 |
| Identitas setelah dedup | 36 |
| Digabung | 14 |
| Terkirim | 29 |
| DLQ awal → setelah putar ulang | 5 → 4 |
| Dipulihkan | 1 |
| Total percobaan | 43 |
| Ambang alarm kedalaman | 5 |
| Bahasa per identitas | ID 29 · EN 5 · DE 2 |

## Yang perlu ditulis di instruksi pemasangan

Bukan "ubah path lalu jalankan". Yang benar:

1. Impor `workflow_ujian.json`.
2. Ubah path di node **Baca CSV** ke tempat `SAB_test_leads_50.csv` diletakkan.
3. Setel `N8N_RESTRICT_FILE_ACCESS_TO` ke folder yang memuat kedua berkas itu,
   atau letakkan keduanya di dalam folder yang sudah diizinkan.
4. Execute Workflow.

Langkah 3 itulah yang tidak tertulis di surat 23 November, dan tanpanya workflow
berhenti di node pertama dengan pesan yang tidak menyebut penyebabnya.

## Perintah lengkap yang dipakai

    N8N_USER_FOLDER=tmp/n8n_bersih N8N_RUNNERS_BROKER_PORT=5799 \
      n8n import:workflow --input=ujian/workflow_ujian.json

    N8N_USER_FOLDER=tmp/n8n_bersih N8N_RUNNERS_BROKER_PORT=5799 \
    N8N_RESTRICT_FILE_ACCESS_TO="<folder proyek>" \
      n8n execute --id=sabujian001

`N8N_RUNNERS_BROKER_PORT` perlu diganti kalau ada instance n8n lain yang hidup
di mesin yang sama — port bawaannya 5679, dan instance kedua akan gagal start
dengan pesan "Task Broker's port 5679 is already in use".
