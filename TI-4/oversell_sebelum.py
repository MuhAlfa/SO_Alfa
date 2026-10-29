#!/usr/bin/env python3
"""I-4 Sistem Operasi Kelas D - Simulasi OVERSELLING (SEBELUM perbaikan).

Kasus: flash sale toko online UMKM. Stok tinggal STOK_AWAL unit, tetapi
PEMBELI orang mencoba checkout bersamaan. Tanpa sinkronisasi, terjadi race
condition pada critical section "cek stok -> kurangi stok".

Pemakaian:  python3 oversell_sebelum.py [jumlah_percobaan]
"""
import random
import sys
import threading
import time

STOK_AWAL = 10
PEMBELI = 50


def jalankan_sekali():
    stok = {"jumlah": STOK_AWAL}
    berhasil = []
    start = threading.Barrier(PEMBELI)  # semua pembeli mulai serentak (flash sale)

    def checkout(pid):
        start.wait()
        # ===== CRITICAL SECTION (TIDAK DILINDUNGI) =====
        if stok["jumlah"] > 0:                       # (1) CHECK
            time.sleep(random.uniform(0, 0.001))     #     latensi DB/pembayaran
            stok["jumlah"] -= 1                      # (2) ACT (read-modify-write)
            berhasil.append(pid)
        # ===============================================

    ts = [threading.Thread(target=checkout, args=(i,)) for i in range(PEMBELI)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    return len(berhasil), stok["jumlah"]


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    print(f"=== SEBELUM PERBAIKAN (tanpa mutex) | stok={STOK_AWAL}, pembeli={PEMBELI} ===")
    print(f"{'Run':<5}{'Pesanan sukses':<16}{'Stok akhir':<12}{'Status'}")
    bermasalah = 0
    for r in range(1, n + 1):
        sukses, sisa = jalankan_sekali()
        oversell = sukses > STOK_AWAL or sisa < 0
        bermasalah += oversell
        print(f"{r:<5}{sukses:<16}{sisa:<12}{'OVERSELLING (+%d)' % (sukses - STOK_AWAL) if oversell else 'ok'}")
    print(f"\nRingkasan: {bermasalah}/{n} percobaan mengalami overselling")
