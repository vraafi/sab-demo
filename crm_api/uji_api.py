"""Uji integrasi CRM API — lewat HTTP sungguhan, bukan panggilan fungsi.

Yang dibuktikan di sini bukan "kodenya jalan", tapi janji-janji yang tertulis
di surat lingkup benar-benar ditegakkan oleh server:

  - percobaan ulang tidak membuat kontak ganda (Idempotency-Key)
  - menulis di atas versi yang sudah basi ditolak (ETag / If-Match)
  - dua sisi mengubah field yang sama -> field itu TIDAK diubah, field lain
    tetap masuk, dan klien diberi tahu lewat 409
  - penghapusan tersebar sebagai tombstone, bukan hilang begitu saja
  - kursor delta hanya bisa maju, tidak bergantung pada jam
  - webhook ditandatangani, punya batas waktu, dan kiriman ganda dikenali

Jalankan: python uji_api.py
Keluar dengan kode 1 kalau ada satu saja yang gagal.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

AKAR = Path(__file__).resolve().parent
KUNCI = "kunci-uji-sab"
RAHASIA = "rahasia-uji-webhook"

lulus = 0
gagal: list[str] = []


def cek(nama: str, syarat: bool, pesan: str = "") -> None:
    global lulus
    if syarat:
        lulus += 1
        print(f"  ok   {nama}")
    else:
        gagal.append(f"{nama}: {pesan}")
        print(f"  GAGAL {nama} — {pesan}")


def porta_bebas() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    n = s.getsockname()[1]
    s.close()
    return n


class Api:
    def __init__(self, dasar: str, kunci: str = KUNCI):
        self.dasar = dasar.rstrip("/")
        self.kunci = kunci

    def panggil(self, metode: str, jalur: str, isi=None, kepala=None):
        data = None if isi is None else json.dumps(isi).encode()
        h = {"Content-Type": "application/json"}
        if self.kunci is not None:
            h["Authorization"] = f"Bearer {self.kunci}"
        h.update(kepala or {})
        req = urllib.request.Request(self.dasar + jalur, data=data, headers=h, method=metode)
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                teks = r.read().decode()
                return r.status, (json.loads(teks) if teks else {}), dict(r.headers)
        except urllib.error.HTTPError as e:
            teks = e.read().decode()
            return e.code, (json.loads(teks) if teks else {}), dict(e.headers)


def tunggu_sehat(api: Api, batas=15.0) -> bool:
    mulai = time.time()
    while time.time() - mulai < batas:
        try:
            kode, _, _ = api.panggil("GET", "/health")
            if kode == 200:
                return True
        except Exception:
            pass
        time.sleep(0.1)
    return False


def tanda(waktu_ms: int, badan: bytes) -> str:
    return hmac.new(RAHASIA.encode(), f"{waktu_ms}.".encode() + badan,
                    hashlib.sha256).hexdigest()


def utama() -> int:
    port = porta_bebas()
    db = AKAR / "_data_uji.json"
    for f in (db, Path(str(db) + ".tmp")):
        if f.exists():
            f.unlink()

    env = dict(os.environ, PORT=str(port), API_KEY=KUNCI,
               WEBHOOK_SECRET=RAHASIA, DB_PATH=str(db))
    proses = subprocess.Popen(
        ["node", str(AKAR / "server.js")],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    api = Api(f"http://127.0.0.1:{port}")
    try:
        if not tunggu_sehat(api):
            keluaran = proses.stdout.read() if proses.stdout else ""
            print("server tidak siap:\n" + keluaran)
            return 1

        print("\n== 1. Kunci API ==")
        kode, isi, _ = Api(f"http://127.0.0.1:{port}", kunci=None).panggil("GET", "/v1/contacts")
        cek("tanpa kunci ditolak 401", kode == 401, f"dapat {kode}")
        kode, isi, _ = Api(f"http://127.0.0.1:{port}", kunci="salah").panggil("GET", "/v1/contacts")
        cek("kunci salah ditolak 401", kode == 401, f"dapat {kode}")

        print("\n== 2. Idempotensi ==")
        kode, isi, _ = api.panggil("POST", "/v1/contacts",
                                   {"id": "K01", "nama": "Siti Rahayu"})
        cek("POST tanpa Idempotency-Key ditolak 428", kode == 428, f"dapat {kode}")

        kode, isi, kepala = api.panggil(
            "POST", "/v1/contacts",
            {"id": "K01", "nama": "Siti Rahayu", "telp": "628110001",
             "kota": "Bandung", "tahap": "baru"},
            {"Idempotency-Key": "buat-K01"})
        cek("POST dengan kunci -> 201", kode == 201, f"dapat {kode}")
        cek("versi awal 1", isi.get("versi") == 1, f"dapat {isi.get('versi')}")
        etag_awal = kepala.get("ETag")
        cek("ETag dikirim", bool(etag_awal), f"dapat {etag_awal!r}")

        kode, isi2, kepala2 = api.panggil(
            "POST", "/v1/contacts",
            {"id": "K01", "nama": "Siti Rahayu", "telp": "628110001",
             "kota": "Bandung", "tahap": "baru"},
            {"Idempotency-Key": "buat-K01"})
        cek("POST ulang dengan kunci sama tidak membuat kontak kedua",
            kode in (200, 201) and isi2.get("versi") == 1, f"dapat {kode} versi {isi2.get('versi')}")
        cek("percobaan ulang ditandai", kepala2.get("Idempotent-Replay") == "true",
            f"dapat {kepala2.get('Idempotent-Replay')!r}")

        kode, isi3, _ = api.panggil("GET", "/v1/contacts")
        cek("hanya ada satu kontak", len(isi3.get("data", [])) == 1,
            f"dapat {len(isi3.get('data', []))}")

        print("\n== 3. Konkurensi optimistis ==")
        kode, isi, kepala = api.panggil("GET", "/v1/contacts/K01")
        cek("GET membawa ETag", bool(kepala.get("ETag")), "kosong")

        kode, isi, _ = api.panggil("PATCH", "/v1/contacts/K01",
                                   {"set": {"kota": "Bogor"}})
        cek("PATCH tanpa base dan tanpa If-Match ditolak 428", kode == 428, f"dapat {kode}")

        kode, isi, _ = api.panggil(
            "PATCH", "/v1/contacts/K01",
            {"base": {"kota": "Bandung"}, "set": {"kota": "Bogor"}},
            {"If-Match": etag_awal})
        cek("PATCH dengan versi benar -> 200", kode == 200, f"dapat {kode}")
        cek("field benar-benar berubah", isi.get("data", {}).get("kota") == "Bogor",
            f"dapat {isi.get('data', {}).get('kota')!r}")

        kode, isi, _ = api.panggil(
            "PATCH", "/v1/contacts/K01",
            {"base": {"kota": "Bandung"}, "set": {"kota": "Surabaya"}},
            {"If-Match": etag_awal})
        cek("PATCH dengan ETag basi ditolak 412", kode == 412, f"dapat {kode}")

        print("\n== 4. Konflik per-field ==")
        # Dua sisi berangkat dari "Bogor". Lokal mengubah tahap, CRM mengubah kota.
        kode, isi, _ = api.panggil(
            "PATCH", "/v1/contacts/K01",
            {"base": {"kota": "Bogor"}, "set": {"kota": "Medan"}})
        cek("sisi CRM mengubah kota -> 200", kode == 200, f"dapat {kode}")

        kode, isi, _ = api.panggil(
            "PATCH", "/v1/contacts/K01",
            {"base": {"kota": "Bogor", "tahap": "baru"},
             "set": {"kota": "Makassar", "tahap": "tertarik"}})
        cek("dua sisi mengubah field sama -> 409", kode == 409, f"dapat {kode}")
        cek("field yang berkonflik TIDAK diubah",
            isi.get("data", {}).get("kota") == "Medan",
            f"dapat {isi.get('data', {}).get('kota')!r} (seharusnya tetap Medan)")
        cek("field lain tetap tersinkron",
            isi.get("data", {}).get("tahap") == "tertarik",
            f"dapat {isi.get('data', {}).get('tahap')!r}")
        cek("konflik menyebut nilai dasar, sekarang, dan usulan",
            isi.get("konflik") and set(isi["konflik"][0]) ==
            {"field", "dasar", "sekarang", "diusulkan"},
            f"dapat {isi.get('konflik')}")

        kode, isi, _ = api.panggil("GET", "/v1/conflicts")
        cek("konflik masuk antrean", len(isi.get("data", [])) == 1,
            f"dapat {len(isi.get('data', []))}")

        kode, isi, _ = api.panggil(
            "POST", "/v1/conflicts/resolve",
            {"id": "K01", "field": "kota", "nilai": "Makassar", "aktor": "rani"})
        cek("keputusan manusia diterapkan -> 200", kode == 200, f"dapat {kode}")
        cek("nilai akhir sesuai keputusan", isi.get("data", {}).get("kota") == "Makassar",
            f"dapat {isi.get('data', {}).get('kota')!r}")

        kode, isi, _ = api.panggil("GET", "/v1/conflicts")
        cek("antrean konflik kosong lagi", len(isi.get("data", [])) == 0,
            f"dapat {len(isi.get('data', []))}")

        print("\n== 5. Kursor delta ==")
        kode, isi, _ = api.panggil("GET", "/v1/contacts?since=0")
        seq_terakhir = isi.get("next_since", 0)
        cek("delta from 0 memuat kontak", len(isi.get("data", [])) == 1,
            f"dapat {len(isi.get('data', []))}")

        kode, isi, _ = api.panggil("GET", f"/v1/contacts?since={seq_terakhir}")
        cek("delta setelah kursor terakhir kosong", len(isi.get("data", [])) == 0,
            f"dapat {len(isi.get('data', []))}")

        api.panggil("PATCH", "/v1/contacts/K01",
                    {"base": {"tahap": "tertarik"}, "set": {"tahap": "klien"}})
        kode, isi, _ = api.panggil("GET", f"/v1/contacts?since={seq_terakhir}")
        cek("perubahan baru muncul di delta", len(isi.get("data", [])) == 1,
            f"dapat {len(isi.get('data', []))}")
        seq_terakhir = isi.get("next_since", seq_terakhir)

        kode, isi, _ = api.panggil("DELETE", "/v1/contacts/K01", {})
        cek("hapus -> 200", kode == 200, f"dapat {kode}")
        kode, isi, _ = api.panggil("GET", f"/v1/contacts?since={seq_terakhir}")
        baris = isi.get("data", [])
        cek("penghapusan tersebar sebagai tombstone",
            len(baris) == 1 and baris[0].get("dihapus") is True,
            f"dapat {baris}")

        print("\n== 6. Webhook ==")
        kode, isi, _ = api.panggil(
            "POST", "/v1/webhooks",
            {"url": f"http://127.0.0.1:{port}/contoh/terima"})
        cek("pendaftaran webhook -> 201", kode == 201, f"dapat {kode}")

        api.panggil("POST", "/v1/contacts",
                    {"id": "K02", "nama": "Budi Hartono"},
                    {"Idempotency-Key": "buat-K02"})

        terkirim = None
        for _ in range(60):
            kode, isi, _ = api.panggil("GET", "/v1/webhooks/deliveries")
            if isi.get("data"):
                terkirim = isi["data"][-1]
                break
            time.sleep(0.05)
        cek("webhook terkirim", terkirim is not None, "tidak ada catatan pengiriman")
        cek("webhook diterima 2xx", bool(terkirim) and 200 <= terkirim["status"] < 300,
            f"status {terkirim and terkirim['status']}")

        print("\n== 7. Tanda tangan dan putar ulang ==")
        badan = json.dumps({"tipe": "uji", "data": {"id": "X"}}).encode()
        url = f"http://127.0.0.1:{port}/contoh/terima"

        def kirim_mentah(kepala: dict) -> int:
            req = urllib.request.Request(url, data=badan, method="POST", headers={
                "Content-Type": "application/json", **kepala})
            try:
                with urllib.request.urlopen(req, timeout=5) as r:
                    return r.status
            except urllib.error.HTTPError as e:
                return e.code

        waktu = int(time.time() * 1000)
        kode = kirim_mentah({"X-Sab-Signature": f"t={waktu},v1={tanda(waktu, badan)}",
                             "X-Sab-Event-Id": "evt-uji-1"})
        cek("tanda tangan sah diterima", kode == 200, f"dapat {kode}")

        kode = kirim_mentah({"X-Sab-Signature": f"t={waktu},v1={tanda(waktu, badan)}",
                             "X-Sab-Event-Id": "evt-uji-1"})
        cek("kiriman ganda tetap 200", kode == 200, f"dapat {kode}")

        kode = kirim_mentah({"X-Sab-Signature": f"t={waktu},v1={'0' * 64}",
                             "X-Sab-Event-Id": "evt-uji-2"})
        cek("tanda tangan salah ditolak 401", kode == 401, f"dapat {kode}")

        tua = waktu - 10 * 60 * 1000
        kode = kirim_mentah({"X-Sab-Signature": f"t={tua},v1={tanda(tua, badan)}",
                             "X-Sab-Event-Id": "evt-uji-3"})
        cek("tanda tangan sah tapi basi ditolak 401", kode == 401, f"dapat {kode}")

        kode = kirim_mentah({"X-Sab-Event-Id": "evt-uji-4"})
        cek("tanpa tanda tangan ditolak 401", kode == 401, f"dapat {kode}")

        print("\n== 8. Jejak audit ==")
        kode, isi, _ = api.panggil("GET", "/v1/audit")
        audit = isi.get("data", [])
        cek("audit mencatat perubahan", len(audit) >= 4, f"dapat {len(audit)}")
        cek("audit menyebut aktor", all("aktor" in a for a in audit), "ada yang kosong")
        aksi = {a["aksi"] for a in audit}
        cek("audit memuat buat, ubah, putuskan, hapus",
            {"buat", "ubah", "putuskan", "hapus"} <= aksi, f"dapat {aksi}")

        print("\n== 9. Kesehatan akhir ==")
        kode, isi, _ = api.panggil("GET", "/health")
        cek("server masih sehat", kode == 200 and isi.get("status") == "ok", f"{kode} {isi}")
        cek("konflik terbuka nol", isi.get("konflik_terbuka") == 0,
            f"dapat {isi.get('konflik_terbuka')}")

    finally:
        proses.terminate()
        try:
            proses.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proses.kill()
        if db.exists():
            shutil.copy(db, AKAR / "data_uji_terakhir.json")
            db.unlink()
        for f in (Path(str(db) + ".tmp"),):
            if f.exists():
                f.unlink()

    print("\n" + "=" * 62)
    if gagal:
        print(f"GAGAL: {len(gagal)} dari {lulus + len(gagal)} uji")
        for g in gagal:
            print("  - " + g)
        return 1
    print(f"LULUS: {lulus}/{lulus} uji integrasi CRM API")
    return 0


if __name__ == "__main__":
    sys.exit(utama())
