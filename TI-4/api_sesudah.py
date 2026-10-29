#!/usr/bin/env python3
"""API Toko Online UMKM - I-4: versi SESUDAH perbaikan (mutex / semaphore).

Hanya memakai pustaka standar Python. Setiap permintaan dilayani satu thread
(ThreadingHTTPServer), sehingga proses dan thread-nya dapat diamati dengan ps/htop.

Endpoint:
  GET  /api/status                     informasi server (PID, jumlah thread)
  GET  /api/produk?kategori=Makanan    katalog produk (tanpa parameter: semua)
  GET  /api/produk?id=P999             detail satu produk
  GET  /api/pelanggan?id=C0001         data pelanggan dan riwayat pesanannya
  POST /api/checkout                   beli, JSON {"id_pelanggan": "...", "id_produk": "...", "jumlah": 1}
"""
import json
import os
import socket
import sqlite3
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

DB = os.environ.get("TOKO_DB", "/opt/toko-umkm/data/toko.db")
HOST = os.environ.get("TOKO_HOST", "127.0.0.1")
PORT = int(os.environ.get("TOKO_PORT", "5000"))
DELAY_MS = int(os.environ.get("TOKO_DELAY_MS", "20"))  # simulasi waktu proses per permintaan
SYNC = os.environ.get("TOKO_SYNC", "mutex")           # mutex | semaphore
# mutex      : threading.Lock         (kunci biner, ada pemilik)
# semaphore  : threading.Semaphore(1) (semaphore biner, hanya 1 thread boleh masuk)
STOK_LOCK = threading.Lock() if SYNC == "mutex" else threading.Semaphore(1)


def db():
    con = sqlite3.connect(DB, timeout=10)
    con.row_factory = sqlite3.Row
    return con


class Handler(BaseHTTPRequestHandler):
    server_version = "TokoUMKM/1.0"

    def kirim(self, kode, data):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(kode)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print(f"{self.address_string()} {fmt % args}", flush=True)

    def do_GET(self):
        url = urlparse(self.path)
        q = parse_qs(url.query)
        time.sleep(DELAY_MS / 1000)
        if url.path == "/api/status":
            return self.kirim(200, {"layanan": "Toko Online UMKM", "host": socket.gethostname(),
                                    "pid": os.getpid(), "thread_aktif": threading.active_count(),
                                    "thread_ini": threading.current_thread().name,
                                    "waktu": datetime.now().isoformat(timespec="seconds")})
        con = db()
        try:
            if url.path == "/api/produk":
                if "id" in q:
                    row = con.execute("SELECT * FROM produk WHERE id_produk=?", (q["id"][0],)).fetchone()
                    return self.kirim(200, dict(row)) if row else self.kirim(404, {"galat": "Produk tidak ditemukan"})
                sql, args = "SELECT * FROM produk", ()
                if "kategori" in q:
                    sql, args = sql + " WHERE kategori=?", (q["kategori"][0],)
                rows = [dict(r) for r in con.execute(sql + " ORDER BY flash_sale DESC, id_produk", args)]
                return self.kirim(200, rows)
            if url.path == "/api/pelanggan":
                idc = q.get("id", [""])[0]
                p = con.execute("SELECT * FROM pelanggan WHERE id_pelanggan=?", (idc,)).fetchone()
                if not p:
                    return self.kirim(404, {"galat": "Pelanggan tidak ditemukan"})
                riwayat = [dict(r) for r in con.execute(
                    "SELECT ps.id, pr.nama, ps.jumlah, ps.total, ps.status, ps.waktu FROM pesanan ps "
                    "JOIN produk pr ON pr.id_produk = ps.id_produk WHERE ps.id_pelanggan=? "
                    "ORDER BY ps.id DESC LIMIT 10", (idc,))]
                return self.kirim(200, dict(p) | {"pesanan_terakhir": riwayat})
        finally:
            con.close()
        self.kirim(404, {"galat": "Endpoint tidak dikenal"})

    def do_POST(self):
        if urlparse(self.path).path != "/api/checkout":
            return self.kirim(404, {"galat": "Endpoint tidak dikenal"})
        try:
            panjang = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(panjang) or b"{}")
            idc, idp, jumlah = data["id_pelanggan"], data["id_produk"], int(data.get("jumlah", 1))
            if jumlah < 1:
                raise ValueError
        except (ValueError, KeyError, TypeError):
            return self.kirim(400, {"galat": "Body harus JSON berisi id_pelanggan, id_produk, jumlah (>= 1)"})
        with STOK_LOCK:  # critical section: cek stok, kurangi stok, catat pesanan
            con = db()
            try:
                if not con.execute("SELECT 1 FROM pelanggan WHERE id_pelanggan=?", (idc,)).fetchone():
                    return self.kirim(404, {"galat": "Pelanggan tidak ditemukan"})
                p = con.execute("SELECT * FROM produk WHERE id_produk=?", (idp,)).fetchone()
                if not p:
                    return self.kirim(404, {"galat": "Produk tidak ditemukan"})
                if p["stok"] < jumlah:
                    return self.kirim(409, {"galat": "Stok tidak mencukupi", "stok": p["stok"]})
                time.sleep(0.01)  # simulasi verifikasi pembayaran
                con.execute("UPDATE produk SET stok = stok - ? WHERE id_produk=?", (jumlah, idp))
                cur = con.execute("INSERT INTO pesanan (id_pelanggan, id_produk, jumlah, total) VALUES (?,?,?,?)",
                                  (idc, idp, jumlah, p["harga"] * jumlah))
                con.commit()
                sisa = p["stok"] - jumlah
            finally:
                con.close()
        self.kirim(201, {"pesan": "Pesanan berhasil", "id_pesanan": cur.lastrowid, "sisa_stok": sisa})


if __name__ == "__main__":
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"API Toko Online UMKM berjalan di http://{HOST}:{PORT} (PID {os.getpid()}), DB={DB}", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass