"""Bangun workflow_poin4.json — sinkronisasi dua arah di n8n.

Sama seperti workflow ujian: dijalankan sungguhan dengan `n8n execute`, dan
keluarannya dibandingkan dengan versi Python sampai nol perbedaan.

Alurnya sengaja pendek, karena poin 4 bukan soal banyak node melainkan soal
aturan per-field:

  Baca berkas -> ambil teks -> parse + gabung (Code) -> tulis hasil

Jalankan: python bangun_workflow4.py
"""
from __future__ import annotations

import json
from pathlib import Path

AKAR = Path(__file__).resolve().parent
MASUK = (AKAR / "data_poin4.json").resolve()
KELUAR = (AKAR / "hasil_poin4_n8n.json").resolve()

LOGIKA = (AKAR / "logika4.js").read_text(encoding="utf-8")

GABUNG = LOGIKA + """

// ---- Node: Gabung ------------------------------------------------------
// Satu berkas berisi tiga sisi: dasar, lokal, jauh. Yang dijalankan di sini
// adalah aturan yang sama dengan sinkron.py — bukan versi yang disederhanakan.
const teks = $json.data;
const data = typeof teks === 'string' ? JSON.parse(teks) : teks;
return [{json: gabung(data)}];
"""


def node(name, tipe, pos, params, **extra):
    d = {"parameters": params, "id": name.lower().replace(" ", "-"),
         "name": name, "type": tipe, "typeVersion": 1, "position": pos}
    d.update(extra)
    return d


def main() -> int:
    nodes = [
        node("Mulai", "n8n-nodes-base.manualTrigger", [0, 0], {}),
        node("Baca Berkas", "n8n-nodes-base.readWriteFile", [200, 0],
             {"fileSelector": str(MASUK), "options": {}}),
        # Ambil teks apa adanya; JSON-nya di-parse di node berikutnya supaya
        # bentuk berkas (objek, bukan daftar) tidak jadi masalah.
        node("Ambil Teks", "n8n-nodes-base.extractFromFile", [400, 0],
             {"operation": "text", "binaryPropertyName": "data", "options": {}}),
        node("Gabung", "n8n-nodes-base.code", [600, 0],
             {"mode": "runOnceForAllItems", "jsCode": GABUNG}),
        node("Jadikan Berkas", "n8n-nodes-base.convertToFile", [800, 0],
             {"operation": "toJson", "mode": "all", "options": {}}),
        node("Tulis Hasil", "n8n-nodes-base.readWriteFile", [1000, 0],
             {"operation": "write", "fileName": str(KELUAR),
              "dataPropertyName": "data", "options": {}}),
    ]

    sambung = {
        "Mulai": {"main": [[{"node": "Baca Berkas", "type": "main", "index": 0}]]},
        "Baca Berkas": {"main": [[{"node": "Ambil Teks", "type": "main", "index": 0}]]},
        "Ambil Teks": {"main": [[{"node": "Gabung", "type": "main", "index": 0}]]},
        "Gabung": {"main": [[{"node": "Jadikan Berkas", "type": "main", "index": 0}]]},
        "Jadikan Berkas": {"main": [[{"node": "Tulis Hasil", "type": "main", "index": 0}]]},
    }

    wf = {
        "id": "sabpoin4001",
        "name": "SAB — Poin 4 sinkron dua arah",
        "nodes": nodes,
        "connections": sambung,
        "settings": {"executionOrder": "v1"},
        "active": False,
    }
    tujuan = AKAR / "workflow_poin4.json"
    tujuan.write_text(json.dumps(wf, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"workflow: {tujuan} ({len(nodes)} node)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
