"""Simpan ringkasan log eksekusi n8n supaya bisa disertakan sebagai bukti.

Yang diambil: per node, berapa item masuk dan keluar di tiap cabang, dan
apakah cabang error terisi. Ini yang membedakan "workflow pernah dijalankan"
dari "workflow dikirim sebagai JSON".

Jalankan setelah: n8n execute --id=sabujian001
"""
from __future__ import annotations

import json
import subprocess
import sys
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
    rd = d["data"]["resultData"]

    ringkas = {
        "status": d.get("status"),
        "mode": d.get("mode"),
        "mulai": d.get("startedAt"),
        "selesai": d.get("stoppedAt"),
        "node": {},
    }
    # Semua putaran disimpan, bukan hanya yang terakhir. Node Kirim berjalan
    # tiga kali (percobaan 1, 2, 3) dan justru itu buktinya percobaan ulang
    # benar-benar terjadi. Versi sebelumnya menimpa, sehingga tiga putaran
    # tampak seperti satu — persis jenis kekeliruan yang membuat log tidak
    # bisa dipercaya.
    for nama, runs in rd.get("runData", {}).items():
        daftar = []
        for run in runs:
            cabang = []
            for items in run.get("data", {}).get("main", []):
                cabang.append(len(items or []))
            daftar.append({"cabang": cabang,
                           "waktu_ms": round(run.get("executionTime") or 0)})
        ringkas["node"][nama] = {"putaran": len(daftar), "jalan": daftar}

    (AKAR / "log_n8n.json").write_text(
        json.dumps(ringkas, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"status   : {ringkas['status']}")
    print(f"node     : {len(ringkas['node'])}")
    for nama, v in ringkas["node"].items():
        cabang = " ".join(str(j["cabang"]) for j in v["jalan"])
        tanda = f" x{v['putaran']}" if v["putaran"] > 1 else ""
        print(f"  {nama:18} cabang={cabang}{tanda}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
