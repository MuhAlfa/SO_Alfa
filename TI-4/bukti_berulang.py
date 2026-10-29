#!/usr/bin/env python3
"""I-4 Sistem Operasi Kelas D - Bukti eksekusi berulang (sebelum vs sesudah perbaikan).

Untuk setiap percobaan skrip ini:
  1. membuat ulang basis data (stok flash sale P999 = 20) di folder sementara,
  2. menjalankan API versi tertentu di port cadangan (default 5001) -> tidak mengganggu toko-api asli,
  3. menjalankan scripts/flash_sale.py (banyak pembeli bersamaan),
  4. membaca stok akhir & jumlah pesanan P999 langsung dari SQLite, lalu menilai konsistensinya.

Pemakaian (dari folder ~/toko-umkm/ti-4):
  python3 bukti_berulang.py sebelum  [ulang] [pembeli]
  python3 bukti_berulang.py mutex    [ulang] [pembeli]
  python3 bukti_berulang.py semaphore [ulang] [pembeli]
"""
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))   # ~/toko-umkm/ti-4
TOKO = os.path.dirname(HERE)                         # ~/toko-umkm (template)
PORT = int(os.environ.get("TOKO_PORT", "5001"))
PRODUK = "P999"

mode = sys.argv[1] if len(sys.argv) > 1 else "sebelum"
ulang = int(sys.argv[2]) if len(sys.argv) > 2 else 10
pembeli = int(sys.argv[3]) if len(sys.argv) > 3 else 100
if mode not in ("sebelum", "mutex", "semaphore"):
    sys.exit("mode harus: sebelum | mutex | semaphore")
api = "api_sebelum.py" if mode == "sebelum" else "api_sesudah.py"


def tunggu_port():
    for _ in range(100):
        try:
            socket.create_connection(("127.0.0.1", PORT), timeout=0.2).close()
            return
        except OSError:
            time.sleep(0.1)
    sys.exit(f"API tidak mau menyala di port {PORT} (port dipakai proses lain?)")


print(f"=== I-4 | versi: {mode} ({api}) | pembeli bersamaan: {pembeli} | {ulang} percobaan ===")
print(f"{'Run':<5}{'Stok awal':<11}{'Pesanan sukses':<16}{'Stok akhir':<12}{'Status'}")
masalah = 0
with tempfile.TemporaryDirectory() as tmp:
    dbfile = os.path.join(tmp, "toko.db")
    for r in range(1, ulang + 1):
        subprocess.run([sys.executable, os.path.join(TOKO, "app", "generate_data.py"), dbfile, "300"],
                       stdout=subprocess.DEVNULL, check=True)
        con = sqlite3.connect(dbfile)
        awal = con.execute("SELECT stok FROM produk WHERE id_produk=?", (PRODUK,)).fetchone()[0]
        pesanan_lama = con.execute("SELECT COUNT(*) FROM pesanan WHERE id_produk=?", (PRODUK,)).fetchone()[0]
        con.close()

        env = dict(os.environ, TOKO_DB=dbfile, TOKO_PORT=str(PORT), TOKO_HOST="127.0.0.1",
                   TOKO_SYNC="semaphore" if mode == "semaphore" else "mutex")
        srv = subprocess.Popen([sys.executable, os.path.join(HERE, api)], env=env,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            tunggu_port()
            subprocess.run([sys.executable, os.path.join(TOKO, "scripts", "flash_sale.py"),
                            "--url", f"http://127.0.0.1:{PORT}/api", "--pembeli", str(pembeli),
                            "--produk", PRODUK], stdout=subprocess.DEVNULL, check=True)
        finally:
            srv.terminate(); srv.wait()

        con = sqlite3.connect(dbfile)
        akhir = con.execute("SELECT stok FROM produk WHERE id_produk=?", (PRODUK,)).fetchone()[0]
        sukses = con.execute("SELECT COUNT(*) FROM pesanan WHERE id_produk=?", (PRODUK,)).fetchone()[0] - pesanan_lama
        con.close()
        oversell = sukses > awal or akhir < 0
        masalah += oversell
        print(f"{r:<5}{awal:<11}{sukses:<16}{akhir:<12}"
              f"{'OVERSELLING (+%d)' % (sukses - awal) if oversell else 'konsisten'}", flush=True)
print(f"\nRingkasan: {masalah}/{ulang} percobaan mengalami overselling")