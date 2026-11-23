"""Simpan ringkasan log eksekusi workflow poin 4.

Sama seperti simpan_log_n8n.py di ujian/: yang diambil adalah bukti bahwa
workflow benar-benar dijalankan, bukan hanya dikirim sebagai JSON.

Jalankan setelah: n8n execute --id=sabpoin4001
"""
from __future__ import annotations

import json
from pathlib import Path

AKAR = Path(__file__).resolve().parent
MENTAH = AKAR / "tmp_exec.json"


def main() -> int:
    if not MENTAH.exists():
        print("tmp_exec.json belum ada; jalankan n8n execute dulu")
        return 1
    teks = MENTAH.read_text(encoding="utf-8", errors="ignore")
    i = teks.find('{\n  "data"')
    if i < 0:
        i = teks.find('{"data"')
    d = json.loads(teks[i:])
    rd = d["data"]["resultData"]["runData"]

    ringkas = {"status": d.get("status"), "mode": d.get("mode"),
               "mulai": d.get("startedAt"), "selesai": d.get("stoppedAt"),
               "node": {}}
    for nama, runs in rd.items():
        daftar = []
        for run in runs:
            cabang = [len(x or []) for x in run.get("data", {}).get("main", [])]
            daftar.append({"cabang": cabang,
                           "waktu_ms": round(run.get("executionTime") or 0)})
        ringkas["node"][nama] = {"putaran": len(daftar), "jalan": daftar}

    (AKAR / "log_n8n.json").write_text(
        json.dumps(ringkas, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"status   : {ringkas['status']}")
    for nama, v in ringkas["node"].items():
        cabang = " ".join(str(j["cabang"]) for j in v["jalan"])
        print(f"  {nama:16} cabang={cabang}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
