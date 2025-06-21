# 📖 Catatan Pena - Bot Toko Digital Telegram

Selamat datang di repository Bot Toko Digital "Catatan Pena"! Ini adalah sebuah bot Telegram canggih yang dirancang untuk mengotomatiskan penjualan produk digital (seperti e-book) dari awal hingga akhir. Bot ini dibangun menggunakan Python dengan framework `python-telegram-bot` dan diintegrasikan dengan payment gateway Duitku.

![Contoh Tampilan Bot](https://cdn.araii.id/a.jpeg)


*(Anda bisa mengganti gambar di atas dengan screenshot atau GIF demo dari bot Anda)*

---

## ✨ Fitur Utama

Bot ini dilengkapi dengan berbagai fitur untuk menciptakan pengalaman e-commerce yang lengkap dan profesional di dalam Telegram:

* **Sapaan Selamat Datang Visual:** Pengguna baru disambut dengan foto dan pesan yang ramah.
* **Katalog Produk Berhalaman (Pagination):** Menampilkan produk secara rapi (4 per halaman) dengan tombol navigasi "Selanjutnya" dan "Sebelumnya".
* **Alur Pembelian Interaktif:** Pengguna dapat memilih produk, melihat invoice konfirmasi, dan melanjutkan ke pembayaran, semuanya melalui tombol.
* **Integrasi Payment Gateway Duitku:** Menerima pembayaran secara aman dan terverifikasi.
* **Tampilan QRIS Langsung di Chat:** Bot secara dinamis membuat dan mengirimkan gambar QRIS langsung ke pengguna.
* **Navigasi Penuh:** Pengguna selalu punya opsi untuk "Kembali", "Batal", atau "Hubungi Admin".
* **Invoice Gambar Otomatis:** Setelah pembayaran berhasil, bot mengirimkan invoice gambar profesional berstempel **LUNAS**.
* **Pengiriman Link Aman:** Link download produk dikirim dalam pesan terpisah yang akan **terhapus otomatis setelah 5 menit**.

---

## 🛠️ Teknologi yang Digunakan

* **Bahasa:** Python 3.9+
* **Framework Bot:** `python-telegram-bot`
* **Web Server (untuk Webhook):** `Flask`
* **Payment Gateway:** [Duitku](https://duitku.com/)
* **Pembuatan Gambar:** `Pillow` (PIL Fork)
* **Pembuatan QR Code:** `qrcode`
* **Lainnya:** `requests`, `pytz`, `apscheduler`

---

## 🚀 Pengaturan & Instalasi

Berikut adalah langkah-langkah untuk menjalankan bot ini di server Anda.

### 1. Prasyarat
* Server/VPS dengan akses terminal (disarankan OS berbasis Linux seperti Ubuntu).
* Python 3.9 atau lebih baru.
* Akun Telegram untuk membuat token bot.
* Akun Duitku yang sudah aktif di mode Produksi.
* Aktifkan Nobu Qris Payment Method di dashboard Duitku

### 2. Instalasi
Clone repository ini ke server Anda:
```bash
git clone [https://github.com/raistech/Telegram-Duitku.git](https://github.com/raistech/Telegram-Duitku.git)
cd Telegram-Duitku
```

Buat dan aktifkan virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

Install semua library yang dibutuhkan:

```bash
pip install --upgrade pip
pip install python-telegram-bot flask requests pytz apscheduler qrcode[pil] Pillow
```
Konfigurasi Langsung di Kode
Buka file .py bot Anda dan cari bagian --- KONFIGURASI UTAMA --- di bagian atas. Ganti semua nilai placeholder GANTI_DENGAN... dengan data Anda yang sebenarnya.
```bash
# --- KONFIGURASI UTAMA ---
TELEGRAM_TOKEN = "GANTI_DENGAN_TOKEN_ANDA"
DUITKU_MERCHANT_CODE = "GANTI_DENGAN_KODE_MERCHANT_ANDA"
DUITKU_API_KEY = "GANTI_DENGAN_API_KEY_ANDA"
YOUR_SERVER_URL = "GANTI_DENGAN_URL_SERVER_ANDA" 
ADMIN_USERNAME = "USERNAME_TELEGRAM_ANDA_TANPA_@"

# --- KATALOG PRODUK ---
# Ganti juga link download di bawah ini
PRODUCTS = {
    "001": {"name": "...", "description": "...", "price": 100, "download_link": "GANTI_DENGAN_LINK_DOWNLOAD_1"},
    # ... produk lainnya
}
```
Konfigurasi Duitku
Pastikan Anda sudah melakukan ini di Dashboard Produksi Duitku Anda:

Whitelist IP: Daftarkan Alamat IP publik server Anda.
Callback URL: Atur ke URL_SERVER_ANDA/duitku_callback. Contoh: https://bot.domainanda.com/duitku_callback.

Menjalankan Bot
Setelah semua konfigurasi di dalam file kode selesai, Anda bisa menjalankan bot dari terminal (dengan venv aktif):
```bash
python3 duitku_bot.py
```

📝 Lisensi
Proyek ini dilisensikan di bawah MIT License.

Dibuat dengan ❤️ oleh Skye (Catatan Pena)
