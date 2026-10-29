#!/usr/bin/env python3
"""I-4 Sistem Operasi Kelas D - Perbaikan OVERSELLING (SESUDAH perbaikan).

Dua solusi:
  mutex      : threading.Lock melindungi critical section (cek + kurangi stok)
  semaphore  : counting semaphore berisi STOK_AWAL token; 1 token = 1 unit stok

Pemakaian:  python3 oversell_sesudah.py [mutex|semaphore] [jumlah_percobaan]
"""
import random
import sys
import threading
import time

STOK_AWAL = 10
PEMBELI = 50


def jalankan_mutex():
    stok = {"jumlah": STOK_AWAL}
    berhasil = []
    mutex = threading.Lock()
    start = threading.Barrier(PEMBELI)

    def checkout(pid):
        start.wait()
        with mutex:                                  # ENTRY SECTION
            # ===== CRITICAL SECTION (dilindungi mutex) =====
            if stok["jumlah"] > 0:
                time.sleep(random.uniform(0, 0.001))
                stok["jumlah"] -= 1
                berhasil.append(pid)
            # ===============================================
        # EXIT SECTION: lock dilepas otomatis oleh 'with'

    ts = [threading.Thread(target=checkout, args=(i,)) for i in range(PEMBELI)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    return len(berhasil), stok["jumlah"]


def jalankan_semaphore():
    token_stok = threading.Semaphore(STOK_AWAL)      # nilai awal = jumlah stok
    berhasil = []
    daftar = threading.Lock()                        # hanya untuk append hasil
    start = threading.Barrier(PEMBELI)

    def checkout(pid):
        start.wait()
        if token_stok.acquire(blocking=False):       # P(): ambil 1 unit, tanpa menunggu
            time.sleep(random.uniform(0, 0.001))     # proses bayar (token sudah milik pembeli)
            with daftar:
                berhasil.append(pid)
        # jika gagal acquire -> stok habis, pesanan ditolak

    ts = [threading.Thread(target=checkout, args=(i,)) for i in range(PEMBELI)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    return len(berhasil), STOK_AWAL - len(berhasil)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "mutex"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    fungsi = {"mutex": jalankan_mutex, "semaphore": jalankan_semaphore}[mode]
    print(f"=== SESUDAH PERBAIKAN ({mode}) | stok={STOK_AWAL}, pembeli={PEMBELI} ===")
    print(f"{'Run':<5}{'Pesanan sukses':<16}{'Stok akhir':<12}{'Status'}")
    bermasalah = 0
    for r in range(1, n + 1):
        sukses, sisa = fungsi()
        oversell = sukses > STOK_AWAL or sisa < 0
        bermasalah += oversell
        print(f"{r:<5}{sukses:<16}{sisa:<12}{'OVERSELLING' if oversell else 'ok'}")
    print(f"\nRingkasan: {bermasalah}/{n} percobaan mengalami overselling")
