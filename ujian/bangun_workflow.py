"""Bangun workflow_ujian.json — workflow n8n untuk ujian 50 lead SAB.

Workflow ini benar-benar dijalankan (`n8n execute`), bukan hanya dikirim
sebagai JSON. Log eksekusinya ikut disertakan.

CATATAN PENTING soal percobaan ulang (ditemukan saat menguji, bukan diduga):

  `retryOnFail` milik n8n mengulang SELURUH node, dan ia hanya menyala kalau
  node gagal sebagai satu kesatuan. Pada node Code dengan mode
  runOnceForEachItem, kegagalan sebagian item ditangkap per item lalu
  dikirim ke cabang error — node-nya sendiri tidak melempar, jadi
  retryOnFail tidak pernah menyala. Ini sudah dibuktikan dengan pengukuran:
  workflow dengan waitBetweenTries 2000 ms selesai dalam 1,9 detik, artinya
  tidak ada penantian percobaan ulang sama sekali.

  Karena itu percobaan ulang dibuat EKSPLISIT di graf: Kirim -> Periksa ->
  Tambah -> kembali ke Kirim. Setiap percobaan jadi terlihat di log eksekusi
  (Kirim dijalankan tiga kali), dan jumlah percobaan disimpan di item, bukan
  di static data — tulisan $getWorkflowStaticData dari node yang melempar
  error memang dibuang, itu juga sudah diukur.

Jalankan: python bangun_workflow.py
"""
from __future__ import annotations

import json
from pathlib import Path

AKAR = Path(__file__).resolve().parent
CSV = (AKAR.parent.parent / "marketing" / "sab" / "SAB_test_leads_50.csv").resolve()
KELUAR = (AKAR / "hasil_ujian_n8n.json").resolve()

LOGIKA = (AKAR / "logika.js").read_text(encoding="utf-8")

PERCOBAAN_MAKS = 3

# ---------------------------------------------------------------- node Code

KIRIM = """
// ---- Node: Kirim -------------------------------------------------------
// Satu item = satu identitas. Node ini sengaja MELEMPAR error untuk
// mensimulasikan kanal yang menolak. Yang nyata di sini adalah
// penanganannya, bukan pengirimannya: tidak ada pesan sungguhan yang
// dikirim ke 50 lead sintetis.
//
// Percobaan ke berapa disimpan di item (`percobaan`), bukan di static data,
// karena tulisan static data dari node yang melempar error dibuang.
if ($json.akan_gagal_permanen) {
  throw new Error('kanal menolak (5xx) pada percobaan ' + $json.percobaan + ': ' + $json.jalur);
}
return {json: {...$json, status: 'terkirim'}};
"""

TERKIRIM = """
// ---- Node: Terkirim ----------------------------------------------------
// Menumpuk yang berhasil ke static data. Node ini tidak pernah melempar,
// jadi tulisannya tersimpan. Dipanggil berkali-kali (sekali per putaran
// percobaan), karena itu hasilnya ditumpuk, bukan ditimpa.
const sd = $getWorkflowStaticData('global');
sd.__terkirim = sd.__terkirim || [];
for (const item of items) {
  sd.__terkirim.push({
    identitas: item.json.id,
    nama: item.json.nama,
    kanal: item.json.jalur,
    percobaan_ke: item.json.percobaan,
  });
}
return items.map(i => ({json: i.json}));
"""

TAMBAH = """
// ---- Node: Tambah percobaan --------------------------------------------
// Satu-satunya tempat keadaan percobaan berubah, dan ia berubah di item —
// ikut mengalir kembali ke node Kirim lewat kabel, bukan lewat memori.
const sd = $getWorkflowStaticData('global');
sd.__ulang = sd.__ulang || {};
sd.__ulang[$json.id] = $json.percobaan;
return {json: {...$json, percobaan: $json.percobaan + 1}};
"""

DLQ = """
// ---- Node: DLQ ---------------------------------------------------------
// Menerima cabang error dari node Kirim SETELAH tiga percobaan. n8n
// mempertahankan data asli item dan menambahkan properti `error`, jadi
// catatan DLQ lengkap: siapa, kanal apa, pesan apa, berapa percobaan.
const sd = $getWorkflowStaticData('global');
sd.__dlq = sd.__dlq || [];
for (const item of items) {
  const j = item.json;
  sd.__dlq.push({
    id: 'DLQ-' + String(sd.__dlq.length + 1).padStart(3, '0'),
    identitas: j.id,
    nama: j.nama,
    kanal: j.jalur || (j.kanal ? j.kanal[j.kanal.length - 1] : ''),
    percobaan: j.percobaan,
    error_message: 'kanal menolak setelah ' + j.percobaan + ' percobaan (5xx)',
    error_n8n: typeof j.error === 'string' ? j.error : (j.error && j.error.message) || '',
    original_payload: {pesan: j.pesan_pertama},
  });
}
return items.map(i => ({json: i.json}));
"""

REKONSILIASI = LOGIKA + """

// ---- Node: Rekonsiliasi ------------------------------------------------
// Membaca hasil yang sudah ditumpuk di static data, bukan dari item yang
// kebetulan lewat. Dengan begitu urutan cabang tidak mengubah jawaban:
// node ini boleh dijalankan berkali-kali dan angka terakhirnya tetap sama.
const sd = $getWorkflowStaticData('global');

const awal = sd.__semua_identitas || [];
const terkirim = sd.__terkirim || [];
const gagal = sd.__dlq || [];
const ulang = sd.__ulang || {};

// Pemutaran ulang DLQ: sebagian pulih setelah penyebabnya diperbaiki.
const pulih = [], sisa = [];
for (const d of gagal) {
  if (acak(d.identitas + '|putar', 'ulang') < 0.55) pulih.push(d); else sisa.push(d);
}

const AMBANG = 5;
const alarmAwal = gagal.length >= AMBANG;
const alarmAkhir = sisa.length >= AMBANG;

const seharusnya = awal.filter(i => !i.dikecualikan && !i.tanpa_saluran).map(i => i.id);
const dapat = new Set([...terkirim.map(t => t.identitas), ...pulih.map(p => p.identitas)]);

const hasil = {
  dijalankan: new Date().toISOString(),
  mesin: 'n8n',
  poin_1_dedup: {
    baris_masuk: sd.__stat ? sd.__stat.baris_masuk : null,
    identitas: sd.__stat ? sd.__stat.identitas : null,
    digabung: sd.__stat ? sd.__stat.digabung : null,
    kontak_dipakai_bersama: sd.__stat ? sd.__stat.kontak_dipakai_bersama : null,
    kemungkinan_duplikat_nama: sd.__stat ? sd.__stat.kemungkinan_duplikat_nama : null,
    kontak_bersama: sd.__bentrok || [],
    kemungkinan_duplikat: sd.__mungkin || [],
  },
  poin_2_bahasa: {
    sebaran: awal.reduce((a, i) => (a[i.bahasa] = (a[i.bahasa] || 0) + 1, a), {}),
  },
  poin_3_optout: {
    opt_out: awal.filter(i => i.optout).map(i => i.id),
    spam: awal.filter(i => i.spam).map(i => i.id),
    lintas_kanal: awal.filter(i => i.lintas).map(i => i.id),
  },
  poin_5_kirim: {
    // Terkirim termasuk yang pulih lewat pemutaran ulang DLQ — sama seperti
    // mesin.py, supaya kedua angka bisa dibandingkan langsung.
    terkirim: terkirim.length + pulih.length,
    dlq_awal: gagal.length,
    dipulihkan: pulih.length,
    dlq_setelah_putar_ulang: sisa.length,
    alarm_saat_kirim: alarmAwal,
    alarm_setelah_putar_ulang: alarmAkhir,
    ambang_alarm: AMBANG,
    // Bukti percobaan ulang benar-benar terjadi: berapa item yang perlu
    // dicoba lebih dari sekali, dan berapa total percobaan yang dijalankan.
    item_dicoba_ulang: Object.keys(ulang).length,
    total_percobaan: terkirim.reduce((a, t) => a + (t.percobaan_ke || 1), 0)
      + gagal.reduce((a, d) => a + (d.percobaan || 0), 0),
    dlq: sisa.map(d => ({id: d.id, identitas: d.identitas, nama: d.nama,
      kanal: d.kanal, percobaan: d.percobaan, error_message: d.error_message})),
    dipulihkan_daftar: pulih.map(p => p.identitas),
  },
  poin_6_rekonsiliasi: {
    seharusnya_dibalas: seharusnya.length,
    benar_benar_dibalas: dapat.size,
    selisih: seharusnya.length - dapat.size,
    pengecualian: seharusnya.filter(i => !dapat.has(i)),
  },
};
return [{json: hasil}];
"""

# state yang perlu dibawa antar-node lewat static data
DEDUP = LOGIKA + """

// ---- Node: Dedup (sekaligus menyimpan state untuk rekonsiliasi) --------
const sd = $getWorkflowStaticData('global');
const rows = items.map(i => i.json);
const hasil = kelompokkan(rows);

// Klasifikasi dilakukan di sini juga supaya rekonsiliasi punya daftar lengkap
// (termasuk yang dikecualikan) tanpa perlu membawa cabang terpisah.
for (const i of hasil.identitas) {
  const semua = i.pesan || [];
  const [bhsAkhir] = bahasa(semua[semua.length - 1] || '');
  const [bhsAwal] = bahasa(semua[0] || '');
  i.bahasa = bhsAkhir !== '??' ? bhsAkhir : bhsAwal;
  i.optout = semua.some(p => optOut(p));
  i.spam = semua.some(p => spam(p));
  i.lintas = new Set(i.kanal).size > 1;
  i.dikecualikan = i.optout || i.spam;
  const [bisa, jalur] = tujuanBisa(i);
  i.tanpa_saluran = bisa ? null : jalur;
  i.jalur = bisa ? jalur : null;
  // Keputusan gagal/tidak ditentukan di sini supaya node Kirim cukup
  // melempar error. Kuncinya sama dengan mesin.py: id + jalur, di-hash
  // FNV-1a, sehingga daftar kegagalan tidak bisa ditebak dari nomor baris.
  if (bisa) {
    const kunci = i.id + '|' + jalur;
    i.akan_gagal_permanen = acak(kunci, 'permanen') < P_PERMANEN;
  }
}

// Wadah hasil dikosongkan di awal setiap eksekusi. Tanpa ini, sisa dari
// eksekusi sebelumnya bisa ikut terhitung.
sd.__stat = hasil.stat;
sd.__bentrok = hasil.bentrok;
sd.__mungkin = hasil.mungkin;
sd.__terkirim = [];
sd.__dlq = [];
sd.__ulang = {};
sd.__semua_identitas = hasil.identitas.map(i => ({
  id: i.id, bahasa: i.bahasa, optout: i.optout, spam: i.spam,
  lintas: i.lintas, dikecualikan: i.dikecualikan, tanpa_saluran: i.tanpa_saluran,
}));

// Yang dikirim hanya yang memang boleh dan bisa dibalas. Yang opt-out, spam,
// atau tanpa saluran tidak pernah masuk node Kirim — bukan dikirim lalu gagal.
const kirim = hasil.identitas.filter(i => !i.dikecualikan && !i.tanpa_saluran);
return kirim.map(i => ({json: {
  id: i.id, nama: i.nama, telp: i.telp, surel: i.surel, kanal: i.kanal,
  baris: i.baris, pesan: i.pesan, pesan_pertama: i.pesan_pertama,
  bahasa: i.bahasa, optout: i.optout, spam: i.spam, lintas: i.lintas,
  dikecualikan: i.dikecualikan, tanpa_saluran: i.tanpa_saluran,
  jalur: i.jalur,
  akan_gagal_permanen: i.akan_gagal_permanen,
  percobaan: 1,
}}));
"""


def node(name, tipe, pos, params, **extra):
    d = {"parameters": params, "id": name.lower().replace(" ", "-"),
         "name": name, "type": tipe, "typeVersion": 1, "position": pos}
    d.update(extra)
    return d


def main() -> int:
    nodes = [
        node("Mulai", "n8n-nodes-base.manualTrigger", [0, 0], {}),
        node("Baca CSV", "n8n-nodes-base.readWriteFile", [200, 0],
             {"fileSelector": str(CSV), "options": {}}),
        node("Parse CSV", "n8n-nodes-base.extractFromFile", [400, 0],
             {"operation": "csv", "binaryPropertyName": "data", "options": {}}),
        node("Dedup", "n8n-nodes-base.code", [600, 0],
             {"mode": "runOnceForAllItems", "jsCode": DEDUP}),
        # Kirim TIDAK memakai retryOnFail: itu mengulang seluruh node dan
        # tidak menyala untuk kegagalan sebagian item. Percobaan ulang ada
        # di graf (Periksa -> Tambah -> Kirim), jadi terlihat di log.
        node("Kirim", "n8n-nodes-base.code", [820, 0],
             {"mode": "runOnceForEachItem", "jsCode": KIRIM},
             onError="continueErrorOutput"),
        node("Terkirim", "n8n-nodes-base.code", [1040, -180],
             {"mode": "runOnceForAllItems", "jsCode": TERKIRIM}),
        node("Periksa", "n8n-nodes-base.if", [1040, 180],
             {"conditions": {"number": [
                 {"value1": "={{ $json.percobaan }}", "operation": "smaller",
                  "value2": PERCOBAAN_MAKS}]}}),
        node("Tambah", "n8n-nodes-base.code", [1260, 180],
             {"mode": "runOnceForEachItem", "jsCode": TAMBAH}),
        node("DLQ", "n8n-nodes-base.code", [1480, 300],
             {"mode": "runOnceForAllItems", "jsCode": DLQ}),
        node("Rekonsiliasi", "n8n-nodes-base.code", [1700, 0],
             {"mode": "runOnceForAllItems", "jsCode": REKONSILIASI}),
        # readWriteFile menulis BINARY, bukan teks. Jadi objek hasil diubah
        # dulu menjadi berkas JSON oleh node Convert to File.
        node("Jadikan Berkas", "n8n-nodes-base.convertToFile", [1900, 0],
             {"operation": "toJson", "mode": "all", "options": {}}),
        node("Tulis Hasil", "n8n-nodes-base.readWriteFile", [2080, 0],
             {"operation": "write", "fileName": str(KELUAR),
              "dataPropertyName": "data", "options": {}}),
    ]

    sambung = {
        "Mulai": {"main": [[{"node": "Baca CSV", "type": "main", "index": 0}]]},
        "Baca CSV": {"main": [[{"node": "Parse CSV", "type": "main", "index": 0}]]},
        "Parse CSV": {"main": [[{"node": "Dedup", "type": "main", "index": 0}]]},
        "Dedup": {"main": [[{"node": "Kirim", "type": "main", "index": 0}]]},
        "Kirim": {"main": [
            [{"node": "Terkirim", "type": "main", "index": 0}],
            [{"node": "Periksa", "type": "main", "index": 0}],
        ]},
        # true  = masih di bawah tiga percobaan -> ulangi
        # false = sudah tiga percobaan -> DLQ
        "Periksa": {"main": [
            [{"node": "Tambah", "type": "main", "index": 0}],
            [{"node": "DLQ", "type": "main", "index": 0}],
        ]},
        "Tambah": {"main": [[{"node": "Kirim", "type": "main", "index": 0}]]},
        "Terkirim": {"main": [[{"node": "Rekonsiliasi", "type": "main", "index": 0}]]},
        "DLQ": {"main": [[{"node": "Rekonsiliasi", "type": "main", "index": 0}]]},
        "Rekonsiliasi": {"main": [[{"node": "Jadikan Berkas", "type": "main", "index": 0}]]},
        "Jadikan Berkas": {"main": [[{"node": "Tulis Hasil", "type": "main", "index": 0}]]},
    }

    wf = {
        "id": "sabujian001",
        "name": "SAB — Ujian 50 lead (enam poin)",
        "nodes": nodes,
        "connections": sambung,
        "settings": {"executionOrder": "v1"},
        "active": False,
    }
    tujuan = AKAR / "workflow_ujian.json"
    tujuan.write_text(json.dumps(wf, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"workflow: {tujuan} ({len(nodes)} node)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
