"""Poin 4 lewat HTTP — sinkron yang sama, tapi ke server sungguhan.

`sinkron.py` membuktikan aturannya benar. `sinkron_api.py` membuktikan aturan
itu masih benar ketika dijalankan lewat jaringan, dengan kunci API, ETag,
Idempotency-Key, tombstone, dan antrean konflik yang disimpan server.

Bedanya penting. Aturan yang hanya lulus di dalam satu proses belum tentu
lulus ketika ada dua penulis, pengiriman ulang, dan urutan yang tidak dijamin.
Di sini semua itu ada.

Urutannya sengaja sama dengan kenyataan: CRM SAB mengubah lebih dulu (09:30),
SAB menyusul (08:10 di jam lokal, tapi yang dikirim belakangan). Jam tidak
dipakai untuk memutuskan apa pun — itu justru yang diuji.

Jalankan: python sinkron_api.py
Menulis: hasil_poin4_api.json
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

AKAR = Path(__file__).resolve().parent
SERVER = AKAR.parent / "crm_api" / "server.js"
KUNCI = "kunci-poin4"
BUKAN_FIELD = {"id", "versi", "updated_at", "dihapus"}


# ---------------------------------------------------------------------------
# Klien
# ---------------------------------------------------------------------------

class Crm:
    def __init__(self, dasar: str):
        self.dasar = dasar.rstrip("/")
        self.panggilan = 0
        self.ulang = 0

    def _kirim(self, metode, jalur, isi=None, kepala=None):
        data = None if isi is None else json.dumps(isi).encode()
        h = {"Content-Type": "application/json",
             "Authorization": f"Bearer {KUNCI}"}
        h.update(kepala or {})
        req = urllib.request.Request(self.dasar + jalur, data=data, headers=h,
                                     method=metode)
        self.panggilan += 1
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                teks = r.read().decode()
                return r.status, (json.loads(teks) if teks else {}), dict(r.headers)
        except urllib.error.HTTPError as e:
            teks = e.read().decode()
            return e.code, (json.loads(teks) if teks else {}), dict(e.headers)

    def sehat(self) -> bool:
        kode, isi, _ = self._kirim("GET", "/health")
        return kode == 200 and isi.get("status") == "ok"

    def buat(self, rec: dict, kunci_idem: str) -> dict:
        isi = {k: v for k, v in rec.items() if k not in BUKAN_FIELD}
        isi["id"] = rec["id"]
        if rec.get("updated_at"):
            isi["updated_at"] = rec["updated_at"]
        kode, jawab, _ = self._kirim("POST", "/v1/contacts", isi,
                                     {"Idempotency-Key": kunci_idem})
        if kode not in (200, 201):
            raise RuntimeError(f"buat {rec['id']} gagal {kode}: {jawab}")
        return jawab

    def ubah(self, cid: str, base: dict, set_: dict) -> tuple[int, dict]:
        return self._kirim("PATCH", f"/v1/contacts/{cid}",
                           {"base": base, "set": set_,
                            "aktor": "sab-sync"})[:2]

    def hapus(self, cid: str) -> int:
        kode, _, _ = self._kirim("DELETE", f"/v1/contacts/{cid}", {})
        return kode

    def semua(self) -> list[dict]:
        keluar, sejak = [], 0
        while True:
            kode, isi, _ = self._kirim("GET", f"/v1/contacts?since={sejak}&limit=1000")
            if kode != 200:
                raise RuntimeError(f"delta gagal {kode}")
            keluar.extend(isi["data"])
            if not isi.get("ada_lagi"):
                return keluar
            sejak = isi["next_since"]

    def konflik(self) -> list[dict]:
        kode, isi, _ = self._kirim("GET", "/v1/conflicts")
        return isi.get("data", [])


def selisih(dasar: dict, sisi: dict) -> dict:
    """Field yang berbeda dari dasar. Hanya itu yang dikirim."""
    beda = {}
    for f in set(dasar) | set(sisi):
        if f in BUKAN_FIELD:
            continue
        a = dasar.get(f) or None
        b = sisi.get(f) or None
        if a != b:
            beda[f] = b
    return beda


def dasar_field(rec: dict) -> dict:
    return {k: v for k, v in rec.items() if k not in BUKAN_FIELD}


# ---------------------------------------------------------------------------
# Jalankan
# ---------------------------------------------------------------------------

def porta_bebas() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    n = s.getsockname()[1]
    s.close()
    return n


def utama() -> int:
    data = json.loads((AKAR / "data_poin4.json").read_text(encoding="utf-8"))
    harap = json.loads((AKAR / "hasil_poin4.json").read_text(encoding="utf-8"))
    dasar = {r["id"]: r for r in data["dasar"]}

    port = porta_bebas()
    db = AKAR / "_data_api.json"
    for f in (db, Path(str(db) + ".tmp")):
        if f.exists():
            f.unlink()

    env = dict(os.environ, PORT=str(port), API_KEY=KUNCI, DB_PATH=str(db))
    proses = subprocess.Popen(["node", str(SERVER)], env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True)
    crm = Crm(f"http://127.0.0.1:{port}")
    try:
        for _ in range(150):
            try:
                if crm.sehat():
                    break
            except Exception:
                pass
            time.sleep(0.1)
        else:
            print("server tidak siap")
            return 1

        # 1. Tanam keadaan dasar.
        for r in data["dasar"]:
            crm.buat(r, f"dasar-{r['id']}")
        print(f"dasar ditanam: {len(data['dasar'])} kontak")

        # 2. Sisi CRM bergerak lebih dulu, termasuk satu penghapusan.
        for r in data["jauh"]:
            d = dasar.get(r["id"])
            if d is None:
                crm.buat(r, f"jauh-{r['id']}")
                continue
            beda = selisih(dasar_field(d), r)
            if beda:
                kode, jawab = crm.ubah(r["id"], dasar_field(d), beda)
                if kode not in (200, 409):
                    raise RuntimeError(f"jauh {r['id']} gagal {kode}: {jawab}")

        id_jauh = {r["id"] for r in data["jauh"]}
        for cid in dasar:
            if cid not in id_jauh:
                kode = crm.hapus(cid)
                if kode != 200:
                    raise RuntimeError(f"hapus {cid} gagal {kode}")
                print(f"  CRM menghapus {cid}")
        print(f"perubahan CRM: {len(data['jauh'])} kontak")

        # 3. SAB menyusul. Inilah saat konflik harus terdeteksi.
        kode_409 = 0
        for r in data["lokal"]:
            d = dasar.get(r["id"])
            if d is None:
                crm.buat(r, f"lokal-{r['id']}")
                continue
            beda = selisih(dasar_field(d), r)
            if not beda:
                continue
            kode, jawab = crm.ubah(r["id"], dasar_field(d), beda)
            if kode == 409:
                kode_409 += 1
            elif kode != 200:
                raise RuntimeError(f"lokal {r['id']} gagal {kode}: {jawab}")
        print(f"perubahan SAB: {len(data['lokal'])} kontak "
              f"({kode_409} permintaan dijawab 409 karena ada field berkonflik)")

        # 4. Baca hasilnya dari server, bukan dari ingatan.
        akhir = {k["id"]: k for k in crm.semua()}
        konflik = crm.konflik()
        hidup = {i: k for i, k in akhir.items() if not k.get("dihapus")}

        print(f"\nhasil di server : {len(hidup)} kontak hidup, "
              f"{len(konflik)} konflik terbuka, "
              f"{len(akhir) - len(hidup)} tombstone")

        # 5. Bandingkan dengan mesin dalam-proses.
        #
        # Yang dibandingkan BUKAN "apakah kedua sisi sama", karena pada field
        # yang berkonflik keduanya memang HARUS berbeda: itu arti konflik.
        # Yang dibandingkan:
        #   - field yang tidak berkonflik: harus identik, tanpa kecuali
        #   - field yang berkonflik: sisi CRM harus tetap memuat nilai CRM
        #     (perubahan orang lain tidak boleh ditimpa), dan catatan
        #     gabungan harus tetap memuat nilai dasar
        #   - daftar konflik: harus sama persis
        bidang_konflik = {}
        for c in harap["konflik"]:
            f = "*" if c["field"] == "*" else c["field"]
            bidang_konflik[(c["id"], f)] = c

        beda_nilai, diperiksa = [], 0
        for g in harap["gabung"]:
            k = hidup.get(g["id"])
            if k is None:
                beda_nilai.append(f"{g['id']}: ada di mesin, tidak ada di server")
                continue
            for f, v in g.items():
                if f in BUKAN_FIELD:
                    continue
                diperiksa += 1
                if (g["id"], f) in bidang_konflik:
                    # Berkonflik: CRM harus tetap pada nilainya sendiri.
                    c = bidang_konflik[(g["id"], f)]
                    if (k.get(f) or None) != (c["jauh"] or None):
                        beda_nilai.append(
                            f"{g['id']}.{f}: berkonflik, sisi CRM seharusnya tetap "
                            f"{c['jauh']!r}, tapi server memuat {k.get(f)!r}")
                    continue
                if (k.get(f) or None) != (v or None):
                    beda_nilai.append(f"{g['id']}.{f}: mesin={v!r} server={k.get(f)!r}")

        # Field yang berkonflik harus tetap pada nilai DASAR di catatan gabungan,
        # bukan pada nilai salah satu sisi. Kalau tidak, ada yang menang diam-diam.
        for (cid, f), c in bidang_konflik.items():
            g = next((x for x in harap["gabung"] if x["id"] == cid), None)
            if g is None or f not in g:
                continue
            diperiksa += 1
            if (g.get(f) or None) != (c["dasar"] or None):
                beda_nilai.append(
                    f"{cid}.{f}: catatan gabungan seharusnya memuat nilai dasar "
                    f"{c['dasar']!r}, tapi memuat {g.get(f)!r} — ada yang menang")

        id_mesin = {g["id"] for g in harap["gabung"]}
        id_server = set(hidup)
        if id_mesin != id_server:
            beda_nilai.append(f"kumpulan id beda: hanya mesin {id_mesin - id_server}, "
                              f"hanya server {id_server - id_mesin}")

        # Konflik: (id, field) harus sama. Nama field penghapusan dipetakan.
        def kunci_konflik(c):
            f = c["field"]
            return (c["id"], "*" if f in ("(dihapus)", "*") else f)

        mesin_k = {kunci_konflik(c) for c in harap["konflik"]}
        server_k = {kunci_konflik(c) for c in konflik}
        if mesin_k != server_k:
            beda_nilai.append(f"konflik beda: hanya mesin {sorted(mesin_k - server_k)}, "
                              f"hanya server {sorted(server_k - mesin_k)}")

        # Isi konflik juga harus sepakat: dasar, nilai jauh, nilai lokal.
        peta_mesin = {kunci_konflik(c): c for c in harap["konflik"]}
        for c in konflik:
            m = peta_mesin.get(kunci_konflik(c))
            if not m or m["field"] == "*":
                continue
            if (m["dasar"] or None) != (c["dasar"] or None):
                beda_nilai.append(f"konflik {c['id']}.{c['field']}: dasar mesin={m['dasar']!r} "
                                  f"server={c['dasar']!r}")
            if (m["jauh"] or None) != (c["sekarang"] or None):
                beda_nilai.append(f"konflik {c['id']}.{c['field']}: jauh mesin={m['jauh']!r} "
                                  f"server={c['sekarang']!r}")
            if (m["lokal"] or None) != (c["diusulkan"] or None):
                beda_nilai.append(f"konflik {c['id']}.{c['field']}: lokal mesin={m['lokal']!r} "
                                  f"server={c['diusulkan']!r}")

        # 6. Bukti jam tidak jadi wasit: C07.
        c07 = hidup.get("C07", {})
        print(f"C07 (CRM updated_at 23:59, SAB 08:16) -> tahap {c07.get('tahap')!r}; "
              f"yang menang yang berubah, bukan yang jamnya paling malam")

        hasil = {
            "ringkasan": {
                "kontak_hidup": len(hidup),
                "konflik_terbuka": len(konflik),
                "tombstone": len(akhir) - len(hidup),
                "permintaan_http": crm.panggilan,
                "jawaban_409": kode_409,
                "nilai_dibandingkan": diperiksa,
                "perbedaan": len(beda_nilai),
            },
            "konflik": konflik,
            "kontak": sorted(hidup.values(), key=lambda x: x["id"]),
        }
        (AKAR / "hasil_poin4_api.json").write_text(
            json.dumps(hasil, ensure_ascii=False, indent=1), encoding="utf-8")

        print(f"nilai dibandingkan : {diperiksa}")
        if beda_nilai:
            print(f"PERBEDAAN          : {len(beda_nilai)}")
            for b in beda_nilai[:12]:
                print("  - " + b)
            return 1
        print("PERBEDAAN          : 0 — mesin dalam-proses dan server HTTP sepakat "
              "pada setiap field")
        return 0
    finally:
        proses.terminate()
        try:
            proses.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proses.kill()
        for f in (db, Path(str(db) + ".tmp")):
            if f.exists():
                f.unlink()


if __name__ == "__main__":
    sys.exit(utama())
