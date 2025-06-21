import os
import uuid
import hashlib
import requests
import threading
import logging
import asyncio
from flask import Flask, request, jsonify
from datetime import datetime, timedelta, timezone

# Import library Telegram
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import Application, CommandHandler, ContextTypes, JobQueue, CallbackQueryHandler

# Import library lainnya
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import qrcode
import io
import math
from PIL import Image, ImageDraw, ImageFont # Library untuk membuat gambar

# --- KONFIGURASI LOGGING ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- KONFIGURASI UTAMA ---
TELEGRAM_TOKEN = "GANTI_DENGAN_TOKEN_ANDA"
DUITKU_MERCHANT_CODE = "GANTI_DENGAN_KODE_MERCHANT_ANDA"
DUITKU_API_KEY = "GANTI_DENGAN_API_KEY_ANDA"
YOUR_SERVER_URL = "GANTI_DENGAN_URL_SERVER_ANDA" 
DUITKU_API_URL = "https://passport.duitku.com/webapi/api/merchant/v2/inquiry"
DUITKU_STATUS_API_URL = "https://passport.duitku.com/webapi/api/merchant/transactionStatus"
ADMIN_USERNAME = "AraiiXBot" #username telegram tanpa '@'
PRODUCTS_PER_PAGE = 4

# --- AKTIFKAN NOBU QRIS PAYMENT METHOD DI DASHBOARD DUITKU ---

# --- KATALOG PRODUK ---
PRODUCTS = {
    "001": {"name": "E-book Yellowface by Rebecca F. Kuang", "description": "Novel satir tahun 2023.", "price": 100, "download_link": "GANTI_DENGAN_LINK_DOWNLOAD_1"},
    "002": {"name": "E-book Atomic Habits by James Clear", "description": "Cara membangun kebiasaan baik.", "price": 100, "download_link": "GANTI_DENGAN_LINK_DOWNLOAD_2"},
    "003": {"name": "E-book The Psychology of Money", "description": "Pelajaran abadi tentang kekayaan.", "price": 100, "download_link": "GANTI_DENGAN_LINK_DOWNLOAD_3"},
    "004": {"name": "E-book Sapiens by Yuval Noah Harari", "description": "Riwayat singkat umat manusia.", "price": 100, "download_link": "GANTI_DENGAN_LINK_DOWNLOAD_4"},
    "005": {"name": "E-book The Alchemist by Paulo Coelho", "description": "Sebuah fabel tentang mengikuti mimpimu.", "price": 100, "download_link": "GANTI_DENGAN_LINK_DOWNLOAD_5"},
}

transactions = {}
application = None 

# --- FUNGSI-FUNGSI BARU & YANG DIUBAH ---

def generate_invoice_image(order_id: str, product_name: str, price: int) -> io.BytesIO | None:
    """Membuat gambar invoice dengan stempel LUNAS."""
    try:
        img_width, img_height = 800, 600
        background_color = (255, 255, 255)
        image = Image.new('RGB', (img_width, img_height), background_color)
        draw = ImageDraw.Draw(image)
        
        try:
            font_reg = ImageFont.truetype("DejaVuSans.ttf", 28)
            font_bold = ImageFont.truetype("DejaVuSans-Bold.ttf", 36)
            font_stamp = ImageFont.truetype("DejaVuSans-Bold.ttf", 90)
        except IOError:
            logging.error("File font DejaVuSans.ttf tidak ditemukan! Pastikan ada di folder bot.")
            font_reg = ImageFont.load_default(); font_bold = ImageFont.load_default(); font_stamp = ImageFont.load_default()

        draw.text((50, 50), "INVOICE LUNAS", font=font_bold, fill=(0, 0, 0))
        draw.line((50, 100, img_width - 50, 100), fill=(0, 0, 0), width=2)
        
        tz_wib = timezone(timedelta(hours=7))
        invoice_date = datetime.now(tz_wib).strftime('%d %B %Y')
        draw.text((50, 120), f"Order ID: {order_id}", font=font_reg, fill=(50, 50, 50))
        draw.text((50, 160), f"Tanggal: {invoice_date}", font=font_reg, fill=(50, 50, 50))

        draw.line((50, 220, img_width - 50, 220), fill=(200, 200, 200), width=1)
        draw.text((50, 240), "Deskripsi", font=font_bold, fill=(0,0,0,150))
        draw.text((img_width - 250, 240), "Total", font=font_bold, fill=(0,0,0,150))
        draw.line((50, 280, img_width - 50, 280), fill=(200, 200, 200), width=1)

        draw.text((50, 300), product_name, font=font_reg, fill=(0, 0, 0))
        draw.text((img_width - 250, 300), f"Rp {price:,}", font=font_reg, fill=(0, 0, 0))

        draw.line((50, 450, img_width - 50, 450), fill=(0, 0, 0), width=2)
        draw.text((50, 470), "Total Pembayaran", font=font_reg, fill=(0, 0, 0))
        draw.text((img_width - 250, 470), f"Rp {price:,}", font=font_bold, fill=(0, 0, 0))
        
        stamp_text = "LUNAS"; stamp_image = Image.new('RGBA', (400, 200), (0,0,0,0)); stamp_draw = ImageDraw.Draw(stamp_image)
        stamp_draw.text((10,10), stamp_text, font=font_stamp, fill=(21, 194, 106, 128)) # Warna hijau semi-transparan
        stamp_image = stamp_image.rotate(30, expand=1)
        image.paste(stamp_image, (200, 250), stamp_image)

        bio = io.BytesIO(); bio.name = 'invoice.png'; image.save(bio, 'PNG'); bio.seek(0)
        return bio
    except Exception as e:
        logging.error(f"Gagal membuat gambar invoice: {e}", exc_info=True)
        return None

async def send_product_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Tugas untuk mengirim invoice, produk, dan menjadwalkan penghapusan."""
    job_data = context.job.data; chat_id = job_data['chat_id']; merchant_order_id = job_data['merchant_order_id']; product_id = job_data['product_id']
    confirm_message = f"✅ <b>Pembayaran Berhasil!</b>\n\nTerima kasih, pembayaran untuk order <code>{merchant_order_id}</code> telah kami terima."
    await context.bot.send_message(chat_id=chat_id, text=confirm_message, parse_mode=ParseMode.HTML)
    if product_id and product_id in PRODUCTS:
        product = PRODUCTS[product_id]
        
        # Buat dan Kirim Invoice Gambar
        invoice_image = generate_invoice_image(order_id=merchant_order_id, product_name=product['name'], price=product['price'])
        if invoice_image:
            await context.bot.send_photo(chat_id=chat_id, photo=invoice_image, caption="Berikut adalah invoice untuk transaksi Anda.")
        else:
            await context.bot.send_message(chat_id=chat_id, text="Gagal membuat file invoice.")
        
        # Kirim Link Download
        download_link = product.get("download_link")
        if download_link and "GANTI_DENGAN_LINK" not in download_link:
            download_message_text = (f"Ini link download Anda untuk produk <b>{product['name']}</b>:\n\n<a href='{download_link}'>KLIK DI SINI UNTUK DOWNLOAD</a>\n\n⚠️ <b>Penting:</b> Pesan ini akan otomatis terhapus dalam <b>5 menit</b>.")
            sent_message = await context.bot.send_message(chat_id=chat_id, text=download_message_text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
            context.job_queue.run_once(delete_message_job, 300, data={'chat_id': sent_message.chat_id, 'message_id': sent_message.message_id}, name=f"delete_{sent_message.message_id}")
            await context.bot.send_message(chat_id=chat_id, text="Ada lagi yang bisa saya bantu?", reply_markup=create_main_menu_keyboard())
        else:
            await context.bot.send_message(chat_id=chat_id, text="Gagal mendapatkan link download produk. Hubungi admin.", reply_markup=create_main_menu_keyboard())
    else:
        await context.bot.send_message(chat_id=chat_id, text="Terjadi kesalahan saat mencari produk Anda. Hubungi admin.", reply_markup=create_main_menu_keyboard())

# --- FUNGSI LAINNYA (TIDAK BERUBAH) ---
def create_main_menu_keyboard():
    keyboard = [[InlineKeyboardButton("📖 Lihat Katalog Produk", callback_data="catalog_page_0")],[InlineKeyboardButton("💬 Hubungi Admin", url=f"https://t.me/{ADMIN_USERNAME}")]]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    reply_markup = create_main_menu_keyboard()
    welcome_message = ("Selamat datang di <b>Catatan Pena</b>!\n\nKami menjual berbagai E-book menarik dengan harga yang sangat murah.\n\nSilakan pilih menu di bawah ini untuk mulai berbelanja.")
    photo_url = "https://cdn.araii.id/a.jpeg" # --- Ubah ini untuk menampilkan Foto Store anda sendiri
    if update.message:
        await update.message.reply_photo(photo=photo_url,caption=welcome_message,reply_markup=reply_markup,parse_mode=ParseMode.HTML)
    elif update.callback_query:
        query = update.callback_query; await query.answer()
        try: await query.message.delete()
        except Exception as e: logging.info(f"Tidak bisa menghapus pesan: {e}")
        await context.bot.send_photo(chat_id=query.message.chat_id,photo=photo_url,caption=welcome_message,reply_markup=reply_markup,parse_mode=ParseMode.HTML)

async def show_catalog_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query; await query.answer()
    try: page = int(query.data.split('_')[-1])
    except (ValueError, IndexError): page = 0
    product_list = list(PRODUCTS.items()); total_products = len(product_list)
    total_pages = math.ceil(total_products / PRODUCTS_PER_PAGE) if total_products > 0 else 1
    start_index = page * PRODUCTS_PER_PAGE; end_index = start_index + PRODUCTS_PER_PAGE
    paginated_products = product_list[start_index:end_index]
    catalog_text = f"📖 <b>Katalog Produk</b> (Halaman {page + 1}/{total_pages})\n"
    keyboard_buttons = []
    if not paginated_products:
        catalog_text += "\nMaaf, tidak ada produk di halaman ini."
    else:
        for product_id, product_data in paginated_products:
            catalog_text += f"\n- - - - - - - - - - - - - - -\n📦 <b>{product_data['name']}</b>\n<i>{product_data['description']}</i>\nHarga: Rp {product_data['price']:,}"
            keyboard_buttons.append([InlineKeyboardButton(f"Beli: {product_data['name']}", callback_data=f"beli_{product_id}")])
    nav_buttons = []
    if page > 0: nav_buttons.append(InlineKeyboardButton("⬅️ Sebelumnya", callback_data=f"catalog_page_{page - 1}"))
    if end_index < total_products: nav_buttons.append(InlineKeyboardButton("Selanjutnya ➡️", callback_data=f"catalog_page_{page + 1}"))
    if nav_buttons: keyboard_buttons.append(nav_buttons)
    keyboard_buttons.append([InlineKeyboardButton("⬅️ Kembali ke Menu Utama", callback_data="main_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard_buttons)
    try:
        await query.edit_message_text(text=catalog_text,reply_markup=reply_markup,parse_mode=ParseMode.HTML)
    except BadRequest as e:
        if "Message is not modified" in str(e): await query.answer("Anda sudah di halaman ini.")
        else: await query.message.delete(); await context.bot.send_message(chat_id=query.message.chat_id,text=catalog_text,reply_markup=reply_markup,parse_mode=ParseMode.HTML)

async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await start(update, context)

async def cancel_qris_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query; await query.answer("Pembayaran dibatalkan."); await start(update, context)

async def beli_produk_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query; await query.answer(); chat_id = query.message.chat_id
    try:
        product_id = query.data.split('_', 1)[1]; product = PRODUCTS.get(product_id)
        if not product: await query.edit_message_text("Error: Produk tidak ditemukan."); return
        await query.edit_message_text(f"Anda memilih: <b>{product['name']}</b>\n\nMembuat invoice, mohon tunggu...", parse_mode=ParseMode.HTML)
        merchant_order_id = f"INV-{product_id}-{uuid.uuid4().hex[:8].upper()}"; transactions[merchant_order_id] = {'chat_id': query.message.chat_id,'product_id': product_id,'status': 'invoicing', 'invoice_message_id': query.message.message_id}
        tz_wib = timezone(timedelta(hours=7)); invoice_date = datetime.now(tz_wib).strftime('%d %B %Y, %H:%M:%S WIB')
        invoice_text = (f"📄 <b>INVOICE</b>\n\n<b>Order ID:</b> <code>{merchant_order_id}</code>\n<b>Tanggal:</b> {invoice_date}\n-----------------------------------------\n<b>Produk:</b> {product['name']}\n<b>Harga:</b> Rp {product['price']:,}\n-----------------------------------------\n<b>TOTAL: Rp {product['price']:,}</b>\n\nSilakan periksa kembali pesanan Anda.")
        keyboard = [[InlineKeyboardButton("✅ Lanjutkan ke Pembayaran", callback_data=f"pay_{merchant_order_id}")], [InlineKeyboardButton("❌ Batalkan & Kembali ke Katalog", callback_data="catalog_page_0")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(invoice_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    except Exception as e: logging.error(f"Error di beli_produk_callback (invoice): {e}", exc_info=True); await query.edit_message_text("Maaf, terjadi kesalahan saat membuat invoice.")

async def process_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query; await query.answer(); chat_id = query.message.chat_id
    try:
        merchant_order_id = query.data.split('_', 1)[1]; transaction_data = transactions.get(merchant_order_id)
        if not transaction_data or transaction_data.get('status') != 'invoicing': await query.edit_message_text("Error: Invoice tidak valid.", reply_markup=create_main_menu_keyboard()); return
        product_id = transaction_data['product_id']; product = PRODUCTS.get(product_id)
        if not product: await query.edit_message_text("Error: Produk pada invoice tidak ditemukan."); return
        await query.edit_message_text(f"Mengkonfirmasi invoice: <b>{merchant_order_id}</b>\n\nMembuat kode QRIS...", parse_mode=ParseMode.HTML)
        payment_amount = product['price']; signature_string = f"{DUITKU_MERCHANT_CODE}{merchant_order_id}{payment_amount}{DUITKU_API_KEY}"; signature = hashlib.md5(signature_string.encode('utf-8')).hexdigest()
        payload = {'merchantCode': DUITKU_MERCHANT_CODE, 'paymentAmount': payment_amount, 'merchantOrderId': merchant_order_id, 'productDetails': product['name'], 'email': f'user_{chat_id}@example.com', 'paymentMethod': 'NQ', 'callbackUrl': f"{YOUR_SERVER_URL}/duitku_callback", 'returnUrl': f"{YOUR_SERVER_URL}/payment_return", 'signature': signature, 'expiryPeriod': 10}
        transactions[merchant_order_id]['status'] = 'pending_payment'
        response = requests.post(DUITKU_API_URL, json=payload, timeout=20); response.raise_for_status(); response_data = response.json()
        qr_string = response_data.get('qrString')
        if qr_string:
            await context.bot.delete_message(chat_id=chat_id, message_id=query.message.message_id)
            qr_image = qrcode.make(qr_string); bio = io.BytesIO(); bio.name = 'qris.png'; qr_image.save(bio, 'PNG'); bio.seek(0)
            caption = (f"Scan QRIS di atas untuk membayar invoice <code>{merchant_order_id}</code>\n<b>{product['name']}</b>\nJumlah: <b>Rp {payment_amount:,}</b>")
            keyboard = [[InlineKeyboardButton("🔄 Cek Status Pembayaran", callback_data=f"status_{merchant_order_id}")],[InlineKeyboardButton("❌ Batalkan", callback_data="cancel_qris")]]
            reply_markup = InlineKeyboardMarkup(keyboard); await context.bot.send_photo(chat_id=chat_id, photo=bio, caption=caption, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        else:
            error_message = response_data.get('Message', 'Gagal mendapatkan data QRIS.'); await context.bot.delete_message(chat_id=chat_id, message_id=query.message.message_id); await context.bot.send_message(chat_id=chat_id, text=f"Gagal membuat QRIS: {error_message}", reply_markup=create_main_menu_keyboard())
    except Exception as e:
        logging.error(f"Error di process_payment_callback: {e}", exc_info=True); await context.bot.send_message(chat_id=chat_id, text="Maaf, terjadi kesalahan internal.", reply_markup=create_main_menu_keyboard())

async def check_status_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query; await query.answer(text="Mengambil status terbaru...", show_alert=False)
    try:
        merchant_order_id = query.data.split('_', 1)[1]; signature_string = f"{DUITKU_MERCHANT_CODE}{merchant_order_id}{DUITKU_API_KEY}"; signature = hashlib.md5(signature_string.encode('utf-8')).hexdigest()
        payload = {'merchantCode': DUITKU_MERCHANT_CODE, 'merchantOrderId': merchant_order_id, 'signature': signature}
        response = requests.post(DUITKU_STATUS_API_URL, json=payload, timeout=20); response.raise_for_status(); response_data = response.json()
        status_code = response_data.get('statusCode'); status_message = response_data.get('statusMessage')
        if status_code == '00': await query.edit_message_caption(caption=f"✅ <b>Pembayaran Berhasil!</b>\n\nInvoice dan link download Anda akan segera dikirim.", reply_markup=None, parse_mode=ParseMode.HTML)
        elif status_code == '01': await query.answer(text="Status masih menunggu pembayaran.", show_alert=True)
        else: await query.message.delete(); await context.bot.send_message(chat_id=query.message.chat_id, text=f"❌ <b>Pembayaran Gagal/Kadaluarsa</b>\n\nStatus: {status_message}.", reply_markup=create_main_menu_keyboard(), parse_mode=ParseMode.HTML)
    except Exception as e: logging.error("Error saat cek status: %s", e); await query.answer(text="Gagal mengambil status.", show_alert=True)

async def delete_message_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    job_data = context.job.data; chat_id = job_data['chat_id']; message_id = job_data['message_id']
    try: await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except BadRequest as e:
        if "Message to delete not found" in str(e): logging.warning(f"JOB: Pesan {message_id} sudah tidak ada.")
        else: logging.error(f"JOB: Gagal menghapus pesan {message_id}: {e}")

# --- APLIKASI WEB SERVER (FLASK) & FUNGSI UTAMA ---
app = Flask(__name__)
def run_flask(): app.run(host='0.0.0.0', port=5051, debug=False)
@app.route('/payment_return', methods=['GET'])
def payment_return(): return "Terima kasih. Silakan kembali ke Telegram."
@app.route('/duitku_callback', methods=['POST'])
def duitku_callback():
    data=request.form; merchant_code=data.get('merchantCode'); amount_str=data.get('amount'); merchant_order_id=data.get('merchantOrderId'); result_code=data.get('resultCode'); signature=data.get('signature')
    if not all([merchant_code, amount_str, merchant_order_id, result_code, signature]): return jsonify({'status': 'error', 'message': 'Invalid callback data'}), 400
    try: amount_int = int(float(amount_str))
    except (ValueError, TypeError): return jsonify({'status': 'error', 'message': 'Invalid amount format'}), 400
    signature_check_string = f"{merchant_code}{amount_int}{merchant_order_id}{DUITKU_API_KEY}"; my_signature = hashlib.md5(signature_check_string.encode('utf-8')).hexdigest()
    if signature != my_signature: return jsonify({'status': 'error', 'message': 'Invalid signature'}), 400
    if merchant_order_id in transactions:
        if result_code == '00':
            if not application: logging.error("Objek 'application' belum diinisialisasi."); return jsonify({'status': 'ok'}), 200
            transaction_info = transactions[merchant_order_id]
            job_data = {'chat_id': transaction_info['chat_id'], 'product_id': transaction_info['product_id'], 'merchant_order_id': merchant_order_id}
            application.job_queue.run_once(send_product_job, 0, data=job_data, name=merchant_order_id)
            del transactions[merchant_order_id]
    return jsonify({'status': 'ok'}), 200

def main() -> None:
    global application
    flask_thread = threading.Thread(target=run_flask); flask_thread.daemon = True; flask_thread.start()
    logging.info("Server Flask berjalan di background pada port 5051...")
    scheduler = AsyncIOScheduler(timezone=pytz.timezone('Asia/Jakarta')); job_queue = JobQueue(); job_queue.scheduler = scheduler
    application = (Application.builder().token(TELEGRAM_TOKEN).job_queue(job_queue).build())
    application.add_handler(CommandHandler("start", start)); application.add_handler(CallbackQueryHandler(show_catalog_callback, pattern='^catalog_page_')); application.add_handler(CallbackQueryHandler(beli_produk_callback, pattern='^beli_')); application.add_handler(CallbackQueryHandler(check_status_callback, pattern='^status_')); application.add_handler(CallbackQueryHandler(main_menu_callback, pattern='^main_menu$')); application.add_handler(CallbackQueryHandler(cancel_qris_callback, pattern='^cancel_qris$')); application.add_handler(CallbackQueryHandler(process_payment_callback, pattern='^pay_'))
    logging.info("Bot Telegram utama memulai polling..."); application.run_polling()

if __name__ == "__main__":
    main()
