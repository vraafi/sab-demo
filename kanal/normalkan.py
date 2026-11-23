"""Enam kanal, enam bentuk, satu catatan lead.

Masalah yang diselesaikan di sini bukan "menyambung API" — itu pekerjaan
pemasangan, dan tiap kanal punya dokumentasinya sendiri. Masalahnya: lima kanal
mengirim lima bentuk yang tidak mirip sama sekali, dan dedup hanya bisa bekerja
kalau semuanya sudah jadi bentuk yang sama lebih dulu.

    WhatsApp (Twilio)  -> WaId tanpa '+', nama dari ProfileName, tanpa email
    Meta Lead Ads      -> field_data berupa array {name, values}
    Google Lead Form   -> user_column_data dengan column_id tetap
    LinkedIn           -> formResponse.answer, nama dipecah firstName/lastName
    Email (IMAP)       -> tidak ada format; nama dan nomor dari tanda tangan
    Form website       -> bebas, karena kita yang membuatnya

Yang sengaja TIDAK dilakukan: mengarang nilai yang tidak ada. Kalau email tidak
memuat nomor telepon, nomornya kosong — bukan ditebak dari domain, bukan diisi
nomor kantor. Satu nomor karangan cukup untuk menggabungkan dua orang berbeda,
dan itu tidak bisa ditarik kembali.

Jalankan: python normalkan.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

AKAR = Path(__file__).resolve().parent
sys.path.insert(0, str(AKAR.parent / "ujian"))

from mesin import surel, telp  # noqa: E402  — normalisasi yang sama dengan mesin dedup


# ---------------------------------------------------------------------------
# Adaptor. Satu fungsi per kanal, semuanya mengembalikan bentuk yang sama.
# ---------------------------------------------------------------------------

def _waktu_iso(w: str) -> str:
    """Semua kanal mengirim waktu dengan format berbeda. Mesin dedup butuh satu
    format untuk mengurutkan anggota satu identitas, jadi disamakan di sini.

    Kalau formatnya tidak dikenali, string aslinya dikembalikan apa adanya —
    lebih baik waktu yang jelek daripada waktu yang dikarang.
    """
    if not w:
        return ""
    w = str(w).strip()
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(w).isoformat()
    except Exception:
        pass
    try:
        from datetime import datetime
        iso = w.replace("Z", "+00:00")
        # Meta mengirim "+0000" tanpa titik dua; fromisoformat butuh "+00:00".
        if len(iso) >= 5 and iso[-5] in "+-" and iso[-3] != ":":
            iso = iso[:-2] + ":" + iso[-2:]
        return datetime.fromisoformat(iso).isoformat()
    except Exception:
        return w


def _dasar(kanal: str, row_id: str, *, nama="", telp_="", surel_="",
           perusahaan="", pesan="", id_kanal="", waktu="") -> dict:
    return {
        "row_id": row_id,
        "channel": kanal,
        "name": nama.strip(),
        "phone": telp_,
        "email": surel_,
        "company": perusahaan,
        "message": pesan,
        "id_kanal": id_kanal,
        "waktu": waktu,
        # Nama yang dipakai mesin dedup. Disamakan di satu tempat supaya tidak
        # ada dua definisi "kapan lead ini masuk".
        "received_at": _waktu_iso(waktu),
        # Disimpan untuk penelusuran: kalau ada yang salah, sumbernya kelihatan.
        "mentah": None,
    }


def dari_whatsapp(p: dict) -> dict:
    """Twilio WhatsApp Sandbox. Nomor di WaId tanpa '+'; nama hanya ada kalau
    pengirim mengisi profil WhatsApp-nya. Email tidak pernah ada di kanal ini."""
    wa = str(p.get("WaId") or "").lstrip("+")
    if not wa:
        wa = str(p.get("From") or "").replace("whatsapp:", "").lstrip("+")
    r = _dasar(
        "whatsapp", "",
        nama=p.get("ProfileName") or "",
        telp_=wa,
        pesan=p.get("Body") or "",
        id_kanal=p.get("MessageSid") or p.get("SmsMessageSid") or "",
        # Twilio tidak mengirim waktu di badan webhook; yang dipakai waktu terima.
        waktu=p.get("_diterima") or "",
    )
    # Kalau ProfileName kosong, WhatsApp tetap mengirim nomor. Lead tanpa nama
    # lebih baik daripada lead yang namanya dikarang dari nomor.
    return r


def dari_meta_lead(p: dict) -> dict:
    """Meta Lead Ads. Nama field ditentukan pemilik form, jadi dipetakan lewat
    daftar sinonim, bukan lewat posisi."""
    kolom = {}
    for f in p.get("field_data") or []:
        nilai = (f.get("values") or [""])[0]
        kolom[str(f.get("name") or "").lower()] = nilai

    def ambil(*kunci: str) -> str:
        for k in kunci:
            if kolom.get(k):
                return kolom[k]
        return ""

    return _dasar(
        "meta_ads_form", "",
        nama=ambil("full_name", "nama_lengkap", "name", "nama"),
        telp_=ambil("phone_number", "phone", "telepon", "nomor_hp"),
        surel_=ambil("email", "surel", "e-mail"),
        perusahaan=ambil("company_name", "perusahaan", "company"),
        pesan="",  # Lead Ads tidak mengirim pesan bebas
        id_kanal=str(p.get("id") or ""),
        waktu=str(p.get("created_time") or ""),
    )


def dari_google_lead(p: dict) -> dict:
    """Google Ads Lead Form Webhook. `column_id` tetap dan berbahasa Inggris,
    jadi lebih stabil daripada Meta. Tidak ada pesan bebas di kanal ini."""
    kolom = {}
    for f in p.get("user_column_data") or []:
        kolom[str(f.get("column_id") or "").upper()] = f.get("string_value") or ""

    return _dasar(
        "google_ads_form", "",
        nama=kolom.get("FULL_NAME", ""),
        telp_=kolom.get("PHONE_NUMBER", ""),
        surel_=kolom.get("EMAIL", ""),
        perusahaan=kolom.get("COMPANY_NAME", ""),
        pesan="",
        id_kanal=str(p.get("lead_id") or ""),
        waktu=p.get("_diterima") or "",
    )


def dari_linkedin_lead(p: dict) -> dict:
    """LinkedIn Lead Gen Forms. Nama dipecah firstName/lastName, nilai dibungkus
    {textValue}, dan submittedAt dalam milidetik."""
    jawab = {}
    for a in ((p.get("formResponse") or {}).get("answer") or []):
        nama_field = ((a.get("formElement") or {}).get("name") or "")
        nilai = a.get("value") or {}
        jawab[nama_field] = nilai.get("textValue") or nilai.get("stringValue") or ""

    depan = jawab.get("firstName", "")
    belakang = jawab.get("lastName", "")

    ms = p.get("submittedAt")
    waktu = ""
    if isinstance(ms, (int, float)):
        from datetime import datetime, timezone
        waktu = datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat()

    return _dasar(
        "linkedin_form", "",
        nama=f"{depan} {belakang}".strip(),
        telp_=jawab.get("phoneNumber", "") or jawab.get("phone", ""),
        surel_=jawab.get("email", ""),
        perusahaan=jawab.get("companyName", ""),
        pesan="",
        id_kanal=str(p.get("id") or ""),
        waktu=waktu,
    )


_POLA_TELP = re.compile(r"(\+62[\s\-]?8[\d\s\-]{7,}|0\d{2,3}[\s\-]?\d{3,4}[\s\-]?\d{3,4})")


def dari_email(p: dict) -> dict:
    """Email masuk lewat IMAP. Tidak ada format, jadi nama diambil dari header
    `from` dan nomor dicari di badan surat — termasuk tanda tangan.

    Ini kanal yang paling rapuh, dan itu bukan alasan untuk melewatinya: kalau
    nomornya tidak ditemukan, lead tetap masuk dengan email saja, lalu dedup
    memutuskan lewat email. Yang tidak boleh terjadi adalah mengarang nomor.
    """
    dari = p.get("from") or ""
    m = re.match(r"\s*\"?([^\"<]+?)\"?\s*<([^>]+)>", dari)
    if m:
        nama, alamat = m.group(1).strip(), m.group(2).strip()
    else:
        nama, alamat = "", dari.strip()

    badan = p.get("body") or ""
    cocok = _POLA_TELP.search(badan)
    nomor = cocok.group(1) if cocok else ""

    return _dasar(
        "email", "",
        nama=nama,
        telp_=nomor,
        surel_=alamat,
        pesan=(p.get("subject") or "") + "\n" + badan,
        id_kanal=p.get("message_id") or "",
        waktu=p.get("date") or "",
    )


def dari_form_web(p: dict) -> dict:
    """Form website. Bentuknya bebas karena kita yang membuatnya — dan justru
    karena itu, kanal ini paling lemah sebagai bukti: form yang dibuat sendiri
    selalu cocok dengan parser-nya sendiri."""
    f = p.get("fields") or {}
    return _dasar(
        "website_form", "",
        nama=f.get("nama") or f.get("name") or "",
        telp_=f.get("telepon") or f.get("phone") or "",
        surel_=f.get("email") or f.get("surel") or "",
        perusahaan=f.get("perusahaan") or f.get("company") or "",
        pesan=f.get("pesan") or f.get("message") or "",
        id_kanal=f"{p.get('form_id','')}:{p.get('submitted_at','')}",
        waktu=p.get("submitted_at") or "",
    )


ADAPTOR = {
    "01_whatsapp_twilio.json": dari_whatsapp,
    "02_meta_lead_ads.json": dari_meta_lead,
    "03_google_lead_form.json": dari_google_lead,
    "04_linkedin_lead_gen.json": dari_linkedin_lead,
    "05_email_imap.json": dari_email,
    "06_form_web_budi.json": dari_form_web,
    "07_form_web_joko.json": dari_form_web,
}


def normalkan(berkas: Path, nomor: int) -> dict:
    adaptor = ADAPTOR[berkas.name]
    mentah = json.loads(berkas.read_text(encoding="utf-8"))
    hasil = adaptor(mentah)
    hasil["row_id"] = f"K{nomor:02d}"
    hasil["mentah"] = {k: v for k, v in mentah.items() if not k.startswith("_")}
    # Normalisasi akhir memakai fungsi yang sama dengan mesin dedup, supaya
    # tidak ada dua aturan normalisasi di satu sistem.
    hasil["_telp"] = telp(hasil["phone"])
    hasil["_surel"] = surel(hasil["email"])
    return hasil


def semua() -> list[dict]:
    keluar = []
    for n, f in enumerate(sorted((AKAR / "contoh").glob("*.json")), start=1):
        if f.name in ADAPTOR:
            keluar.append(normalkan(f, n))
    return keluar


def main() -> int:
    baris = semua()
    print(f"{'baris':6} {'kanal':16} {'nama':16} {'telp':16} {'surel':34} id_kanal")
    print("-" * 118)
    for r in baris:
        print(f"{r['row_id']:6} {r['channel']:16} {r['name'][:15]:16} "
              f"{r['_telp'][:15]:16} {r['_surel'][:33]:34} {r['id_kanal'][:22]}")
    print(f"\n{len(baris)} baris dari {len({r['channel'] for r in baris})} kanal "
          f"-> satu bentuk yang sama.")
    (AKAR / "hasil_normalisasi.json").write_text(
        json.dumps(baris, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
