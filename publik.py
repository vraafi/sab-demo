"""Gerbang untuk alamat publik (Cloudflare Tunnel).

Kenapa berkas ini ada
---------------------
Selama demo hanya hidup di 127.0.0.1, semua tombolnya wajar: saya yang menekan,
saya yang menanggung akibatnya. Begitu demo punya alamat yang bisa dibuka siapa
saja, tiga tombol berubah sifat:

  * ``POST /api/bersihkan`` mengosongkan sesi. Kalau ada yang menekannya saat
    Tico sedang menonton, layarnya berubah tanpa sebab yang terlihat.
  * ``POST /api/kirim-uji`` mengeluarkan pesan WhatsApp sungguhan dari nomor
    kami, dan membakar jatah kirim yang disiapkan untuk panggilan.
  * ``GET /api/lead`` membuka daftar kontak. Sebagian adalah lead milik Tico.

Ditambah ``POST /api/masuk`` yang memeriksa kunci ke CRM: di internet, itu
permukaan tebak-tebakan yang tidak pernah kita minta.

Jadi, di alamat publik:

  1. Satu tautan bertoken. Tanpa token, tidak ada halaman yang terbuka.
  2. Tiga rute di atas ditutup (403), bukan disembunyikan — supaya jelas.
  3. Pengiriman WhatsApp dimatikan lewat ``SAB_TANPA_KIRIM=1``. Pesan tetap
     dibaca, diputuskan, dan dibalas penuh; yang berhenti hanya langkah kirim.
  4. Pemeriksaan kunci dan pemrosesan pesan dibatasi per alamat IP.

Yang **tidak** dilakukan: menyembunyikan bahwa ini demo. Halaman tetap
mengatakan apa adanya bahwa pesan masuk lewat formulir, bukan dari WhatsApp
pengunjung, karena aplikasi ini belum berlangganan WABA.

Cara pakai
----------
    set SAB_TOKEN=<token acak>          # Windows
    export SAB_TOKEN=<token acak>       # bash
    uvicorn app:app --port 8899

Lalu tautan yang dibagikan: ``https://<alamat>/pintu?k=<token>``
Sekali dibuka, cookie 7 hari dipasang, dan tautannya boleh dilupakan.
"""

from __future__ import annotations

import hmac
import os
import time
from collections import defaultdict, deque
from urllib.parse import parse_qs

from starlette.responses import JSONResponse, PlainTextResponse, RedirectResponse

TOKEN = (os.environ.get("SAB_TOKEN") or "").strip()
AKTIF = bool(TOKEN)

# Rute yang tidak dibuka di alamat publik.
TUTUP = frozenset({"/api/kirim-uji", "/api/bersihkan", "/api/lead"})

# (maksimum permintaan, jendela detik) per alamat IP.
BATAS = {
    "/api/masuk": (12, 60.0),    # cukup untuk mencoba salah dan benar berkali-kali
    "/api/coba": (30, 60.0),     # cukup untuk menguji, tidak cukup untuk membanjiri
}

UMUR_COOKIE = 7 * 24 * 3600


def _ip(scope) -> str:
    """Alamat asli pengunjung. Cloudflare menaruhnya di header, bukan di socket."""
    for k, v in scope.get("headers") or []:
        if k == b"cf-connecting-ip":
            return v.decode("latin-1")
    client = scope.get("client") or ("?", 0)
    return str(client[0])


def _cookie(scope, nama: str) -> str:
    for k, v in scope.get("headers") or []:
        if k == b"cookie":
            for bagian in v.decode("latin-1").split(";"):
                a, _, b = bagian.strip().partition("=")
                if a == nama:
                    return b
    return ""


def _sama(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


class Gerbang:
    """Middleware ASGI. Dipasang hanya kalau SAB_TOKEN diisi."""

    def __init__(self, app):
        self.app = app
        self.jejak: dict[str, deque] = defaultdict(deque)

    async def __call__(self, scope, receive, send):
        if not AKTIF or scope["type"] != "http":
            return await self.app(scope, receive, send)

        jalur = scope.get("path", "/")

        # --- Pintu masuk: tukar token di tautan menjadi cookie -------------
        if jalur == "/pintu":
            q = parse_qs((scope.get("query_string") or b"").decode("latin-1"))
            k = (q.get("k") or [""])[0]
            if k and _sama(k, TOKEN):
                r = RedirectResponse("/siaran", status_code=303)
                r.set_cookie("sab", TOKEN, max_age=UMUR_COOKIE, httponly=True,
                             samesite="lax", secure=True, path="/")
                return await r(scope, receive, send)
            r = PlainTextResponse(
                "Tautan ini tidak berlaku.\n\n"
                "Tautan demo hanya berlaku untuk yang menerimanya. Kalau Anda "
                "merasa seharusnya bisa masuk, minta tautannya dikirim ulang.",
                status_code=403)
            return await r(scope, receive, send)

        # --- Semua jalur lain butuh cookie ---------------------------------
        if not _sama(_cookie(scope, "sab"), TOKEN):
            r = PlainTextResponse(
                "Butuh tautan demo.\n\n"
                "Halaman ini hanya terbuka lewat tautan yang dibagikan. "
                "Minta tautannya ke pengirim.",
                status_code=403)
            return await r(scope, receive, send)

        # --- Rute yang ditutup ---------------------------------------------
        if jalur in TUTUP:
            r = JSONResponse(
                {"galat": "Rute ini tidak dibuka di alamat publik. "
                          "Ada di mesin lokal, dan diperlihatkan saat panggilan."},
                status_code=403)
            return await r(scope, receive, send)

        # --- Batas per alamat IP -------------------------------------------
        if jalur in BATAS:
            maks, jendela = BATAS[jalur]
            ip = _ip(scope)
            d = self.jejak[ip]
            sekarang = time.time()
            while d and sekarang - d[0] > jendela:
                d.popleft()
            if len(d) >= maks:
                r = JSONResponse(
                    {"galat": f"Terlalu banyak permintaan dari alamat ini "
                              f"({maks} per {int(jendela)} detik). "
                              f"Coba lagi sebentar lagi."},
                    status_code=429)
                return await r(scope, receive, send)
            d.append(sekarang)

        return await self.app(scope, receive, send)
