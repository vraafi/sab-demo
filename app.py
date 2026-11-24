"""Lapisan HTTP produksi untuk demo SAB — FastAPI + uvicorn.

Yang berubah dari `demo_server.py`: hanya transportnya. Seluruh logika
(kirim, putuskan, periksa kunci, rekam gagal) tetap di modul yang sama dan tetap
diaudit oleh ujian yang sama, karena logika yang sudah lulus sepuluh kasus tidak
boleh ditulis ulang hanya demi terlihat modern.

Yang didapat dari pemisahan ini:
  * `/docs` — OpenAPI yang bisa dibuka Tico sendiri, tanpa saya menjelaskan.
  * Validasi masukan lewat Pydantic, bukan `if not pesan: return ...` yang
    berserakan.
  * Kode status HTTP yang benar (422 untuk masukan salah, 502 untuk mesin mati).
  * Satu proses ASGI yang bisa dijalankan di belakang reverse proxy saat
    produksi, tanpa mengubah satu baris logika.

Menjalankan:
    python app.py                     # port 8899
    uvicorn app:app --port 8899       # cara produksi
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

import demo_server as inti
from coba import HTML as COBA_HTML
from masuk import HTML as MASUK_HTML
from siaran import HTML as SIARAN_HTML

SAB = Path(__file__).resolve().parent
CONFIG = SAB / "config.json"

app = FastAPI(
    title="SAB — mesin demo",
    version="1.0.0",
    description=(
        "Enam poin yang diminta SAB, dijalankan pada sistem yang hidup. "
        "Setiap endpoint di bawah ini adalah tombol yang sama dengan yang ada "
        "di halaman demo — bukan contoh yang disiapkan.\n\n"
        "Pesan masuk di `/api/coba` disimulasikan lewat formulir, bukan dari "
        "WhatsApp pengunjung: aplikasi ini belum berlangganan ke WABA. Setelah "
        "pintu masuk, jalurnya sama persis dengan pesan sungguhan."
    ),
)


# ---------------------------------------------------------------------------
# Bentuk masukan. Batas panjang di sini bukan hiasan: ia menahan kiriman
# raksasa sebelum menyentuh mesin.
# ---------------------------------------------------------------------------
class PesanMasuk(BaseModel):
    pesan: str = Field(..., min_length=1, max_length=600)
    nama: str = Field("", max_length=40)
    tujuan: str = Field("", max_length=20, description="Kosongkan untuk nomor uji")


class Kredensial(BaseModel):
    kunci: str = Field(..., max_length=200)


class Konfigurasi(BaseModel):
    kirim: dict = Field(default_factory=dict)


def baca_config() -> dict:
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    except Exception:                                        # noqa: BLE001
        return {}


# ---------------------------------------------------------------------------
# Gerbang publik. Hanya aktif kalau SAB_TOKEN diisi; di mesin sendiri tidak ada
# yang berubah. Lihat publik.py untuk alasan tiap rute yang ditutup.
# ---------------------------------------------------------------------------
if os.environ.get("SAB_TOKEN"):
    from publik import Gerbang

    app.add_middleware(Gerbang)


# ---------------------------------------------------------------------------
# Halaman
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def konsol() -> str:
    return inti.HALAMAN


@app.get("/siaran", response_class=HTMLResponse, include_in_schema=False)
def siaran() -> str:
    # Penanda untuk halaman: di alamat publik, dua tombol yang mengeluarkan
    # pesan sungguhan dan membuka daftar kontak menutup diri sendiri.
    if inti.TANPA_KIRIM:
        return SIARAN_HTML.replace("<body>", "<body><script>window.__publik=true;</script>", 1)
    return SIARAN_HTML


@app.get("/coba", response_class=HTMLResponse, include_in_schema=False)
def coba() -> str:
    return COBA_HTML


@app.get("/masuk", response_class=HTMLResponse, include_in_schema=False)
def masuk() -> str:
    return MASUK_HTML


@app.get("/demo", response_class=HTMLResponse, include_in_schema=False)
def demo() -> str:
    return inti.DEMO_HTML


# ---------------------------------------------------------------------------
# API — tombol yang sama dengan di layar
# ---------------------------------------------------------------------------
@app.post("/api/coba", tags=["demo"],
          summary="Satu pesan dari pengunjung, diproses sistem yang hidup")
def api_coba(m: PesanMasuk) -> JSONResponse:
    d = inti.coba_pesan(m.pesan, m.nama, m.tujuan)
    if not d.get("ok") and d.get("galat"):
        raise HTTPException(status_code=422, detail=d["galat"])
    return JSONResponse(d)


@app.post("/api/masuk", tags=["keamanan"],
          summary="Periksa kredensial ke CRM (penolakan datang dari CRM)")
def api_masuk(k: Kredensial) -> JSONResponse:
    d = inti.masuk(k.kunci)
    if not d.get("ok"):
        # 401 kalau CRM menolak, 502 kalau CRM-nya sendiri tidak menjawab.
        kode = 401 if d.get("http") == 401 else 502
        raise HTTPException(status_code=kode, detail=d.get("galat"))
    return JSONResponse(d)


@app.post("/api/kirim-uji", tags=["demo"],
          summary="Kirim satu pesan WhatsApp sungguhan lewat jalur lengkap")
def api_kirim() -> JSONResponse:
    return JSONResponse(inti.kirim_uji())


@app.post("/api/bersihkan", tags=["demo"], summary="Mulai sesi baru")
def api_bersihkan() -> JSONResponse:
    return JSONResponse(inti.bersihkan_sesi())


@app.get("/api/status", tags=["mesin"], summary="n8n, CRM, jalur publik")
def api_status() -> JSONResponse:
    return JSONResponse(inti.status_sistem())


@app.get("/api/wa", tags=["mesin"], summary="Kiriman terakhir dan daftar gagal")
def api_wa() -> JSONResponse:
    return JSONResponse(inti.keadaan_wa())


@app.get("/api/lead", tags=["data"], summary="Kontak yang layak ditampilkan")
def api_lead() -> JSONResponse:
    return JSONResponse(inti.daftar_lead())


@app.get("/api/kesiapan", tags=["mesin"],
         summary="Gerbang kesiapan (17 pemeriksaan, di-cache 120 detik)")
def api_kesiapan(segarkan: int = 0) -> JSONResponse:
    return JSONResponse(inti.kesiapan(bool(segarkan)))


@app.get("/api/demo", tags=["demo"], summary="Enam poin, dijalankan saat diminta")
def api_demo() -> JSONResponse:
    try:
        return JSONResponse(inti.jalankan_demo())
    except Exception as e:                                   # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(e)[:300]) from e


@app.get("/api/config", tags=["konfigurasi"],
         summary="Nilai yang berlaku sekarang — untuk diperiksa, bukan ditebak")
def api_config() -> JSONResponse:
    c = baca_config()
    # Di alamat publik, nomor uji disamarkan: Tico cukup tahu bahwa ada satu
    # nomor penerima, tidak perlu nomor utuhnya terbaca siapa saja yang punya
    # tautan.
    if inti.TANPA_KIRIM:
        n = c.get("nomor") or {}
        if n.get("uji"):
            n["uji"] = str(n["uji"])[:4] + "••••••" + str(n["uji"])[-2:]
    c["_berlaku"] = {
        "kirim_maks_per_sesi": inti.KIRIM_MAKS,
        "kirim_jeda_detik": int(inti.KIRIM_JEDA),
        "nomor_uji": c.get("nomor", {}).get("uji"),
        "tunnel": bool(inti.alamat_tunnel()),
        "tanpa_kirim": inti.TANPA_KIRIM,
    }
    return JSONResponse(c)


def main() -> int:
    import uvicorn

    cfg = baca_config().get("server", {})
    port = int(cfg.get("port", 8899))
    print(f"Konsol demo : http://127.0.0.1:{port}")
    print(f"Dokumentasi : http://127.0.0.1:{port}/docs")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
