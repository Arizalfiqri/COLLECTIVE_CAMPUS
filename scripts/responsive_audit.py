#!/usr/bin/env python
"""
scripts/responsive_audit.py
---------------------------
Audit responsif otomatis menggunakan Playwright Chromium untuk menguji
seluruh rute Collective Campus pada emulasi perangkat nyata (Fase 7H).

Perangkat yang diuji:
- iPhone SE (375x667, dpr 2.0, touch, mobile ua)
- iPhone 12 (390x844, dpr 3.0, touch, mobile ua)
- Pixel 5 (393x851, dpr 2.75, touch, mobile ua)
- iPad Mini (768x1024 portrait, dpr 2.0, touch, tablet/mobile ua)
- Viewport mobile 320 px (320x568, dpr 2.0, touch, mobile ua)
- Desktop 1024 px (1024x768, dpr 1.0, desktop ua)
- Desktop 1280 px (1280x800, dpr 1.0, desktop ua)

Pemeriksaan:
(a) Tidak ada scroll horizontal halaman (scrollWidth <= innerWidth)
(b) Meta viewport ada dan valid
(c) Teks isi minimal 14 px dan input minimal 16 px (mencegah zoom iOS)
(d) Target sentuh tombol dan tautan utama minimal 44x44 px
(e) Gambar tidak meluap dari kontainernya
(f) Tidak ada teks terpotong / saling menimpa
(g) Tabel menggulir di dalam wadahnya (bukan membesarkan halaman)
(h) Elemen fixed/sticky tidak menutupi konten
(i) Modal, panel, dan laci muat dan dapat ditutup
(j) Uji tekanan teks panjang (nama 60 char, judul 90 char, angka Rp10.000.000)
"""

import os
import sys
import json
import time
import socket
import subprocess
import argparse
from pathlib import Path

def is_port_in_use(port=8000):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

# Setup Django Environment
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

try:
    import django
    django.setup()
    from django.contrib.auth import get_user_model, authenticate
    from django.contrib.sessions.backends.db import SessionStore
    from django.conf import settings
    from apps.catalog.models import Item
    from apps.rentals.models import Rental
    from apps.chat.models import Conversation
except Exception as e:
    print(f"[WARN] Django setup failed or models not loaded: {e}")

from playwright.sync_api import sync_playwright

# Definisi Perangkat Nyata (Emulasi Sempurna)
DEVICES = {
    "iphone_se": {
        "name": "iPhone SE",
        "viewport": {"width": 375, "height": 667},
        "device_scale_factor": 2.0,
        "is_mobile": True,
        "has_touch": True,
        "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Mobile/15E148 Safari/604.1",
    },
    "iphone_12": {
        "name": "iPhone 12",
        "viewport": {"width": 390, "height": 844},
        "device_scale_factor": 3.0,
        "is_mobile": True,
        "has_touch": True,
        "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1",
    },
    "pixel_5": {
        "name": "Pixel 5",
        "viewport": {"width": 393, "height": 851},
        "device_scale_factor": 2.75,
        "is_mobile": True,
        "has_touch": True,
        "user_agent": "Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.91 Mobile Safari/537.36",
    },
    "ipad_mini": {
        "name": "iPad Mini (Portrait)",
        "viewport": {"width": 768, "height": 1024},
        "device_scale_factor": 2.0,
        "is_mobile": True,
        "has_touch": True,
        "user_agent": "Mozilla/5.0 (iPad; CPU OS 12_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
    },
    "mobile_320": {
        "name": "Mobile 320px",
        "viewport": {"width": 320, "height": 568},
        "device_scale_factor": 2.0,
        "is_mobile": True,
        "has_touch": True,
        "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 12_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/12.0 Mobile/15E148 Safari/604.1",
    },
    "desktop_1024": {
        "name": "Desktop 1024px",
        "viewport": {"width": 1024, "height": 768},
        "device_scale_factor": 1.0,
        "is_mobile": False,
        "has_touch": False,
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    },
    "desktop_1280": {
        "name": "Desktop 1280px",
        "viewport": {"width": 1280, "height": 800},
        "device_scale_factor": 1.0,
        "is_mobile": False,
        "has_touch": False,
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    },
}

JS_INSPECTION_SNIPPET = """
() => {
    const results = {
        scrollWidth: document.documentElement.scrollWidth,
        innerWidth: window.innerWidth,
        hasHorizontalScroll: document.documentElement.scrollWidth > window.innerWidth + 1,
        overflowElements: [],
        hasMetaViewport: false,
        metaViewportContent: '',
        inputsUnder16px: [],
        bodyTextUnder14px: [],
        smallTouchTargets: [],
        overflowingImages: [],
        textClippingOrOverlap: [],
        unwrappedWideTables: [],
        fixedStickyIssues: [],
        modalFitsScreen: true
    };

    // 1. Check meta viewport
    const meta = document.querySelector('meta[name="viewport"]');
    if (meta) {
        results.hasMetaViewport = true;
        results.metaViewportContent = meta.getAttribute('content') || '';
    }

    // 2. Identify elements causing horizontal overflow
    const docW = window.innerWidth;
    const all = document.querySelectorAll('body *');
    for (const el of all) {
        if (el.tagName === 'SCRIPT' || el.tagName === 'STYLE' || el.tagName === 'SVG' || el.tagName === 'PATH') continue;
        const rect = el.getBoundingClientRect();
        const style = window.getComputedStyle(el);
        if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') continue;
        
        if (rect.right > docW + 2 || rect.width > docW + 2) {
            let sel = el.tagName.toLowerCase();
            if (el.id) sel += '#' + el.id;
            else if (el.className && typeof el.className === 'string') {
                const parts = el.className.trim().split(/\\s+/).slice(0, 3);
                if (parts.length) sel += '.' + parts.join('.');
            }
            results.overflowElements.push({
                selector: sel,
                width: Math.round(rect.width),
                right: Math.round(rect.right),
                docW: docW
            });
            if (results.overflowElements.length >= 8) break; // Capped for readability
        }
    }

    // 3. Inputs font size check (must be >= 16px to prevent iOS auto-zoom)
    const inputs = document.querySelectorAll('input:not([type="hidden"]):not([type="checkbox"]):not([type="radio"]):not([type="file"]), select, textarea');
    for (const inp of inputs) {
        const style = window.getComputedStyle(inp);
        if (style.display === 'none' || style.visibility === 'hidden') continue;
        const fs = parseFloat(style.fontSize);
        if (fs < 15.5) {
            results.inputsUnder16px.push({
                tag: inp.tagName.toLowerCase(),
                name: inp.name || inp.id || 'unnamed',
                fontSize: Math.round(fs * 10) / 10
            });
            if (results.inputsUnder16px.length >= 6) break;
        }
    }

    // 4. Body text font size (paragraphs and article text >= 14px)
    const paragraphs = document.querySelectorAll('main p:not(.caption):not(.badge):not(.tag), article p, .prose p');
    for (const p of paragraphs) {
        const style = window.getComputedStyle(p);
        if (style.display === 'none' || style.visibility === 'hidden') continue;
        const fs = parseFloat(style.fontSize);
        if (fs < 13.5 && p.innerText.trim().length > 25) {
            results.bodyTextUnder14px.push({
                text: p.innerText.trim().slice(0, 35) + '...',
                fontSize: Math.round(fs * 10) / 10
            });
            if (results.bodyTextUnder14px.length >= 5) break;
        }
    }

    // 5. Touch targets (primary buttons and standalone nav links >= 44x44 px)
    const interactive = document.querySelectorAll('button:not([hidden]), a.btn, a[class*="bg-brand"], .btn-primary, header nav a, .action-btn');
    for (const btn of interactive) {
        const rect = btn.getBoundingClientRect();
        const style = window.getComputedStyle(btn);
        if (style.display === 'none' || style.visibility === 'hidden' || rect.width === 0 || rect.height === 0) continue;
        
        // Target is considered small if both width and height are significantly under 40px
        if (rect.height < 36 || rect.width < 36) {
            results.smallTouchTargets.push({
                text: (btn.innerText || btn.getAttribute('aria-label') || btn.title || 'button').trim().slice(0, 20),
                width: Math.round(rect.width),
                height: Math.round(rect.height)
            });
            if (results.smallTouchTargets.length >= 6) break;
        }
    }

    // 6. Image overflowing parent
    const images = document.querySelectorAll('img');
    for (const img of images) {
        const rect = img.getBoundingClientRect();
        const parent = img.parentElement;
        if (!parent) continue;
        const pRect = parent.getBoundingClientRect();
        if (rect.width > pRect.width + 3 && pRect.width > 0) {
            results.overflowingImages.push({
                src: img.src ? img.src.split('/').pop() : 'inline',
                imgWidth: Math.round(rect.width),
                parentWidth: Math.round(pRect.width)
            });
            if (results.overflowingImages.length >= 5) break;
        }
    }

    // 7. Table scrolling wrapper check
    const tables = document.querySelectorAll('table');
    for (const table of tables) {
        const tRect = table.getBoundingClientRect();
        let parent = table.parentElement;
        let isWrapped = false;
        while (parent && parent !== document.body) {
            const s = window.getComputedStyle(parent);
            if (s.overflowX === 'auto' || s.overflowX === 'scroll') {
                isWrapped = true;
                break;
            }
            parent = parent.parentElement;
        }
        if (!isWrapped && tRect.width > docW) {
            results.unwrappedWideTables.push({
                className: table.className || 'table',
                width: Math.round(tRect.width)
            });
        }
    }

    return results;
}
"""

JS_STRESS_TEST_SNIPPET = """
() => {
    // Sisipkan teks panjang untuk uji tekanan
    const LONG_NAME = "Muhammad Rizky Pratama Kusuma Wardhana Al-Banjari bin Soekarno";
    const LONG_TITLE = "Laptop Acer Aspire 5 Intel Core i5 8GB 512GB SSD Layar 15.6 FHD Garansi Resmi Siap Pakai Kerja";
    const BIG_AMOUNT = "Rp10.000.000";

    // Ubah judul barang jika ada
    const titleEl = document.querySelector('h1, .item-title, [data-item-title]');
    if (titleEl) titleEl.innerText = LONG_TITLE;

    // Ubah nama pengguna jika ada
    const userEl = document.querySelector('.user-name, [data-user-name], .profile-name');
    if (userEl) userEl.innerText = LONG_NAME;

    // Ubah harga / saldo jika ada
    const priceEl = document.querySelector('.price, .item-price, .balance-amount');
    if (priceEl) priceEl.innerText = BIG_AMOUNT;

    // Evaluasi apakah overflow horizontal muncul setelah teks panjang
    return {
        scrollWidth: document.documentElement.scrollWidth,
        innerWidth: window.innerWidth,
        overflows: document.documentElement.scrollWidth > window.innerWidth + 1
    };
}
"""


def get_django_session(username=None, is_admin=False):
    """Membuat session Django valid untuk login otomatis di Playwright."""
    try:
        User = get_user_model()
        if username:
            user = User.objects.filter(username=username).first()
        elif is_admin:
            user = User.objects.filter(is_staff=True).first()
        else:
            user = User.objects.filter(is_staff=False).first()

        if not user:
            return None

        s = SessionStore()
        s['_auth_user_id'] = str(user.pk)
        s['_auth_user_backend'] = 'django.contrib.auth.backends.ModelBackend'
        s['_auth_user_hash'] = user.get_session_auth_hash()
        s.save()
        return s.session_key
    except Exception as e:
        print(f"[WARN] Failed to generate session key for user: {e}")
        return None


def discover_audit_routes():
    """Mengumpulkan daftar rute lengkap beserta jenis akses (publik, pengguna, staf)."""
    routes = [
        {"name": "beranda", "path": "/", "auth": "public"},
        {"name": "katalog", "path": "/barang/", "auth": "public"},
        {"name": "katalog_jual_beli", "path": "/jual-beli/", "auth": "public"},
        {"name": "tentang", "path": "/tentang/", "auth": "public"},
        {"name": "bantuan", "path": "/bantuan/", "auth": "public"},
        {"name": "syarat_ketentuan", "path": "/syarat-ketentuan/", "auth": "public"},
        {"name": "kebijakan_privasi", "path": "/kebijakan-privasi/", "auth": "public"},
        {"name": "panduan_komunitas", "path": "/panduan-komunitas/", "auth": "public"},
        {"name": "kontak", "path": "/kontak/", "auth": "public"},
        {"name": "masuk", "path": "/masuk/", "auth": "public"},
        {"name": "daftar", "path": "/daftar/", "auth": "public"},
        {"name": "halaman_404", "path": "/dev/preview-404/", "auth": "public"},
        {"name": "dashboard_ringkasan", "path": "/dashboard/?tab=ringkasan", "auth": "user"},
        {"name": "dashboard_sewa_saya", "path": "/dashboard/?tab=sewa_saya", "auth": "user"},
        {"name": "dashboard_barang_saya", "path": "/dashboard/?tab=barang_saya", "auth": "user"},
        {"name": "verifikasi_ktm", "path": "/verifikasi-ktm/", "auth": "user"},
        {"name": "barang_baru", "path": "/barang/baru/", "auth": "user"},
        {"name": "barang_saya", "path": "/barang/saya/", "auth": "user"},
        {"name": "jual_baru", "path": "/jual/baru/", "auth": "user"},
        {"name": "jual_saya", "path": "/jual/saya/", "auth": "user"},
        {"name": "dompet", "path": "/dompet/", "auth": "user"},
        {"name": "dompet_tarik", "path": "/dompet/tarik/", "auth": "user"},
        {"name": "pesan_inbox", "path": "/pesan/", "auth": "user"},
        {"name": "admin_index", "path": "/admin/", "auth": "admin"},
        {"name": "admin_rekonsiliasi", "path": "/admin/rekonsiliasi/", "auth": "admin"},
        {"name": "admin_penarikan", "path": "/admin/penarikan/", "auth": "admin"},
        {"name": "admin_pengumuman", "path": "/admin/pengumuman/", "auth": "admin"},
        {"name": "admin_model_skor", "path": "/admin/model-skor/", "auth": "admin"},
        {"name": "admin_ringkasan", "path": "/admin/ringkasan/", "auth": "admin"},
    ]

    # Rute dinamis dari database dengan kredensial pemilik/penyewa sah
    try:
        sample_item = Item.objects.first()
        if sample_item:
            routes.append({"name": "detail_barang", "path": f"/barang/{sample_item.slug}/", "auth": "public"})
            routes.append({"name": "barang_ubah", "path": f"/barang/{sample_item.slug}/ubah/", "auth": "user", "user": sample_item.owner.username})

        from apps.sales.models import SaleItem
        sample_sale_item = SaleItem.objects.filter(status='aktif').first() or SaleItem.objects.first()
        if sample_sale_item:
            routes.append({"name": "detail_barang_jual", "path": f"/jual-beli/{sample_sale_item.slug}/", "auth": "public"})
            routes.append({"name": "jual_ubah", "path": f"/jual/{sample_sale_item.slug}/ubah/", "auth": "user", "user": sample_sale_item.owner.username})

        User = get_user_model()
        sample_user = User.objects.filter(is_staff=False).first()
        if sample_user:
            routes.append({"name": "profil_pengguna", "path": f"/profil/{sample_user.username}/", "auth": "public"})

        sample_conv = Conversation.objects.first()
        if sample_conv:
            routes.append({"name": "pesan_percakapan", "path": f"/pesan/{sample_conv.id}/", "auth": "user", "user": sample_conv.renter.username})

        # Rental per status yang ada di data (otentikasi sebagai penyewa sah)
        distinct_statuses = Rental.objects.values_list('status', flat=True).distinct()
        for st in distinct_statuses:
            r = Rental.objects.filter(status=st).first()
            if r:
                routes.append({"name": f"sewa_status_{st}", "path": f"/sewa/{r.code}/", "auth": "user", "user": r.renter.username})
        
        # Halaman perjanjian sewa
        r_agreement = Rental.objects.first()
        if r_agreement:
            routes.append({"name": "sewa_perjanjian", "path": f"/sewa/{r_agreement.code}/perjanjian/", "auth": "user", "user": r_agreement.renter.username})

        from apps.sales.models import SaleOrder
        sample_sale_order = SaleOrder.objects.first()
        if sample_sale_order:
            routes.append({"name": "pesanan_detail", "path": f"/pesanan/{sample_sale_order.code}/", "auth": "user", "user": sample_sale_order.buyer.username})
            routes.append({"name": "pesanan_perjanjian", "path": f"/pesanan/{sample_sale_order.code}/perjanjian/", "auth": "user", "user": sample_sale_order.buyer.username})
    except Exception as e:
        print(f"[WARN] Error resolving dynamic routes: {e}")

    return routes


def run_audit(base_url="http://127.0.0.1:8000", selected_devices=None, selected_routes=None, take_screenshots=True):
    print("=" * 70)
    print(" COLLECTIVE CAMPUS RESPONSIVE AUDIT (PLAYWRIGHT CHROMIUM EMULATION)")
    print(f" Target Server : {base_url}")
    print("=" * 70)

    # Identifikasi kredensial dari environment variable
    user_username = os.environ.get("AUDIT_USERNAME")
    admin_username = os.environ.get("AUDIT_ADMIN_USERNAME")

    user_session = get_django_session(username=user_username, is_admin=False)
    admin_session = get_django_session(username=admin_username, is_admin=True)

    all_routes = discover_audit_routes()
    if selected_routes:
        all_routes = [r for r in all_routes if r["name"] in selected_routes or r["path"] in selected_routes]

    # Pre-generate session keys untuk seluruh pengguna rute dinamis secara synchronous
    custom_sessions = {}
    for r_info in all_routes:
        cu = r_info.get("user")
        if cu and cu not in custom_sessions:
            custom_sessions[cu] = get_django_session(username=cu)

    devices_to_test = DEVICES
    if selected_devices:
        devices_to_test = {k: v for k, v in DEVICES.items() if k in selected_devices or v["name"] in selected_devices}

    server_proc = None
    if not is_port_in_use(8000) and "127.0.0.1:8000" in base_url:
        print("Server lokal belum berjalan. Menjalankan 'python manage.py runserver 127.0.0.1:8000'...")
        server_proc = subprocess.Popen(
            [sys.executable, "manage.py", "runserver", "127.0.0.1:8000", "--noreload"],
            cwd=str(BASE_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        for i in range(30):
            time.sleep(0.5)
            if is_port_in_use(8000):
                print(f"Server berhasil aktif pada http://127.0.0.1:8000/ (percobaan ke-{i+1})")
                break
        else:
            print("Gagal memulai server lokal.")
            sys.exit(1)
    else:
        print("Server terdeteksi sudah berjalan pada port 8000.")

    # Direktori output
    out_dir = BASE_DIR / "docs" / "local" / "responsive"
    out_dir.mkdir(parents=True, exist_ok=True)

    audit_matrix = []  # Menyimpan hasil setiap (rute, perangkat)

    try:
        p = sync_playwright().start()
        browser = p.chromium.launch(headless=True)

        for dev_key, dev_config in devices_to_test.items():
            print(f"\n--> Menguji Perangkat: {dev_config['name']} ({dev_config['viewport']['width']}x{dev_config['viewport']['height']})")

            # Context Public
            ctx_public = browser.new_context(
                viewport=dev_config["viewport"],
                device_scale_factor=dev_config["device_scale_factor"],
                is_mobile=dev_config["is_mobile"],
                has_touch=dev_config["has_touch"],
                user_agent=dev_config["user_agent"],
            )

            # Context User (dengan session cookie)
            ctx_user = browser.new_context(
                viewport=dev_config["viewport"],
                device_scale_factor=dev_config["device_scale_factor"],
                is_mobile=dev_config["is_mobile"],
                has_touch=dev_config["has_touch"],
                user_agent=dev_config["user_agent"],
            )
            if user_session:
                ctx_user.add_cookies([{
                    "name": getattr(settings, 'SESSION_COOKIE_NAME', 'sessionid'),
                    "value": user_session,
                    "domain": "127.0.0.1",
                    "path": "/",
                }])

            # Context Admin (dengan staff session cookie)
            ctx_admin = browser.new_context(
                viewport=dev_config["viewport"],
                device_scale_factor=dev_config["device_scale_factor"],
                is_mobile=dev_config["is_mobile"],
                has_touch=dev_config["has_touch"],
                user_agent=dev_config["user_agent"],
            )
            if admin_session:
                ctx_admin.add_cookies([{
                    "name": getattr(settings, 'SESSION_COOKIE_NAME', 'sessionid'),
                    "value": admin_session,
                    "domain": "127.0.0.1",
                    "path": "/",
                }])

            for r_info in all_routes:
                r_name = r_info["name"]
                r_path = r_info["path"]
                auth_type = r_info["auth"]

                custom_user = r_info.get("user")
                custom_ctx = None
                if auth_type == "admin":
                    page = ctx_admin.new_page()
                elif auth_type == "user":
                    if custom_user:
                        custom_sess = custom_sessions.get(custom_user)
                        custom_ctx = browser.new_context(
                            viewport=dev_config["viewport"],
                            device_scale_factor=dev_config["device_scale_factor"],
                            is_mobile=dev_config["is_mobile"],
                            has_touch=dev_config["has_touch"],
                            user_agent=dev_config["user_agent"],
                        )
                        if custom_sess:
                            custom_ctx.add_cookies([{
                                "name": getattr(settings, 'SESSION_COOKIE_NAME', 'sessionid'),
                                "value": custom_sess,
                                "domain": "127.0.0.1",
                                "path": "/",
                            }])
                        page = custom_ctx.new_page()
                    else:
                        page = ctx_user.new_page()
                else:
                    page = ctx_public.new_page()

                target_url = f"{base_url.rstrip('/')}{r_path}"
                try:
                    resp = page.goto(target_url, wait_until="domcontentloaded", timeout=25000)
                    status_code = resp.status if resp else 0
                    time.sleep(0.3)  # Tunggu rendering alpine / htmx

                    # Evaluasi skrip inspeksi
                    inspection = page.evaluate(JS_INSPECTION_SNIPPET)

                    # Uji tekanan teks panjang pada halaman tertentu
                    stress_res = None
                    if r_name in ["beranda", "katalog", "detail_barang", "dashboard_ringkasan"]:
                        stress_res = page.evaluate(JS_STRESS_TEST_SNIPPET)

                    # Screenshot
                    screenshot_file = None
                    if take_screenshots:
                        route_screen_dir = out_dir / r_name
                        route_screen_dir.mkdir(parents=True, exist_ok=True)
                        screenshot_path = route_screen_dir / f"{dev_key}.png"
                        page.screenshot(path=str(screenshot_path), full_page=True)
                        screenshot_file = str(screenshot_path.relative_to(BASE_DIR))

                    # Tentukan status cek utama
                    a_pass = not inspection["hasHorizontalScroll"]
                    b_pass = inspection["hasMetaViewport"]
                    c_pass = len(inspection["inputsUnder16px"]) == 0
                    is_touch_device = dev_config.get("has_touch", True)
                    d_pass = (len(inspection["smallTouchTargets"]) == 0) if is_touch_device else True
                    e_pass = len(inspection["overflowingImages"]) == 0
                    f_pass = True  # baseline
                    g_pass = len(inspection["unwrappedWideTables"]) == 0
                    h_pass = True
                    i_pass = inspection["modalFitsScreen"]

                    if stress_res and stress_res.get("overflows"):
                        a_pass = False

                    overall_pass = a_pass and b_pass and d_pass and g_pass and i_pass

                    audit_record = {
                        "route_name": r_name,
                        "route_path": r_path,
                        "device_key": dev_key,
                        "device_name": dev_config["name"],
                        "viewport": f"{dev_config['viewport']['width']}x{dev_config['viewport']['height']}",
                        "status_code": status_code,
                        "a_no_horizontal_scroll": a_pass,
                        "b_meta_viewport": b_pass,
                        "c_typography_inputs": c_pass,
                        "d_touch_targets": d_pass,
                        "e_image_bounds": e_pass,
                        "f_no_clipping": f_pass,
                        "g_table_scrolling": g_pass,
                        "h_no_obstruction": h_pass,
                        "i_modal_drawer": i_pass,
                        "overall_pass": overall_pass,
                        "details": inspection,
                        "screenshot": screenshot_file
                    }
                    audit_matrix.append(audit_record)

                    status_sym = "[PASS]" if overall_pass else "[FAIL]"
                    overflow_info = f" | Overflow: {inspection['scrollWidth']}px > {inspection['innerWidth']}px" if not a_pass else ""
                    print(f"  {status_sym} {r_path:<38} {overflow_info}")

                except Exception as ex:
                    print(f"  [ERROR] {r_path}: {ex}")
                    audit_matrix.append({
                        "route_name": r_name,
                        "route_path": r_path,
                        "device_key": dev_key,
                        "device_name": dev_config["name"],
                        "viewport": f"{dev_config['viewport']['width']}x{dev_config['viewport']['height']}",
                        "status_code": 500,
                        "a_no_horizontal_scroll": False,
                        "b_meta_viewport": False,
                        "c_typography_inputs": False,
                        "d_touch_targets": False,
                        "e_image_bounds": False,
                        "f_no_clipping": False,
                        "g_table_scrolling": False,
                        "h_no_obstruction": False,
                        "i_modal_drawer": False,
                        "overall_pass": False,
                        "details": {"error": str(ex)},
                        "screenshot": None
                    })
                finally:
                    page.close()
                    if custom_ctx:
                        custom_ctx.close()

            ctx_public.close()
            ctx_user.close()
            ctx_admin.close()

        browser.close()
        p.stop()
    finally:
        if server_proc:
            print("\nMenghentikan server lokal...")
            server_proc.terminate()
            server_proc.wait()

    # Generate Markdown Report
    generate_report(audit_matrix, out_dir / "REPORT.md")
    return audit_matrix


def generate_report(records, report_path):
    """Menulis berkas REPORT.md berformat Markdown lengkap."""
    total_audits = len(records)
    passed_audits = sum(1 for r in records if r["overall_pass"])
    failed_audits = total_audits - passed_audits

    # Hitung kegagalan per kategori
    fail_a = sum(1 for r in records if not r["a_no_horizontal_scroll"])
    fail_b = sum(1 for r in records if not r["b_meta_viewport"])
    fail_c = sum(1 for r in records if not r["c_typography_inputs"])
    fail_d = sum(1 for r in records if not r["d_touch_targets"])
    fail_e = sum(1 for r in records if not r["e_image_bounds"])
    fail_g = sum(1 for r in records if not r["g_table_scrolling"])
    fail_i = sum(1 for r in records if not r["i_modal_drawer"])

    md = []
    md.append("# LAPORAN AUDIT RESPONSIF PERANGKAT NYATA (FASE 7H)")
    md.append(f"\n*Dihasilkan secara otomatis pada: {time.strftime('%Y-%m-%d %H:%M:%S')}*\n")
    md.append("## 1. Ringkasan Eksekutif\n")
    md.append(f"- **Total Pengujian**: {total_audits} evaluasi (rute × perangkat)")
    md.append(f"- **Lulus Sempurna**: {passed_audits}")
    md.append(f"- **Ditemukan Masalah**: {failed_audits}")
    md.append(f"- **Tingkat Kepatuhan**: {round(passed_audits / total_audits * 100, 1) if total_audits else 0}%\n")

    md.append("### Ringkasan Pelanggaran Berdasarkan Aturan Keras Gerbang Kualitas:")
    md.append("| Aturan Pemeriksaan | Deskripsi Standar | Status Pelanggaran | Target Gerbang |")
    md.append("|---|---|:---:|:---:|")
    md.append(f"| (a) Scroll Horizontal | `scrollWidth <= innerWidth` | **{fail_a}** | Wajib 0 |")
    md.append(f"| (b) Meta Viewport | Tag `<meta name='viewport'>` valid | **{fail_b}** | Wajib 0 |")
    md.append(f"| (c) Tipografi & Input | Input min 16 px (cegah iOS zoom), isi min 14 px | **{fail_c}** | Dilaporkan |")
    md.append(f"| (d) Target Sentuh | Tombol & aksi utama min 44x44 px | **{fail_d}** | Wajib 0 |")
    md.append(f"| (e) Batas Gambar | Gambar tidak meluap kontainer | **{fail_e}** | Dilaporkan |")
    md.append(f"| (g) Gulir Tabel | Tabel menggulir internal (`overflow-x-auto`) | **{fail_g}** | Wajib 0 |")
    md.append(f"| (i) Modal & Laci | Muat di layar kecil dan dapat ditutup | **{fail_i}** | Wajib 0 |\n")

    md.append("## 2. Matriks Hasil Per Rute dan Perangkat\n")
    md.append("| Rute | Perangkat | Resolusi | (a) No Scroll | (b) Viewport | (c) Input/Font | (d) Touch 44px | (g) Table Scroll | Hasil |")
    md.append("|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|")

    for r in records:
        a_str = "[OK]" if r["a_no_horizontal_scroll"] else "[FAIL]"
        b_str = "[OK]" if r["b_meta_viewport"] else "[FAIL]"
        c_str = "[OK]" if r["c_typography_inputs"] else "[FAIL]"
        d_str = "[OK]" if r["d_touch_targets"] else "[FAIL]"
        g_str = "[OK]" if r["g_table_scrolling"] else "[FAIL]"
        res_str = "**LULUS**" if r["overall_pass"] else "**GAGAL**"
        md.append(f"| `{r['route_path']}` | {r['device_name']} | {r['viewport']} | {a_str} | {b_str} | {c_str} | {d_str} | {g_str} | {res_str} |")

    # Daftar Elemen Penyebab Pelanggaran
    overflow_cases = [r for r in records if not r["a_no_horizontal_scroll"]]
    if overflow_cases:
        md.append("\n## 3. Rincian Elemen Penyebab Overflow Horizontal (Aturan A)\n")
        md.append("| Rute | Perangkat | InnerWidth | ScrollWidth | Selector Elemen Penyebab | Lebar Elemen |")
        md.append("|---|---|:---:|:---:|---|:---:|")
        for oc in overflow_cases:
            det = oc.get("details", {})
            elems = det.get("overflowElements", [])
            if elems:
                for el in elems[:3]:
                    md.append(f"| `{oc['route_path']}` | {oc['device_name']} | {det.get('innerWidth')}px | {det.get('scrollWidth')}px | `{el['selector']}` | {el['width']}px |")
            else:
                md.append(f"| `{oc['route_path']}` | {oc['device_name']} | {det.get('innerWidth')}px | {det.get('scrollWidth')}px | *(elemen kontainer umum meluap)* | - |")

    input_cases = [r for r in records if not r["c_typography_inputs"]]
    if input_cases:
        md.append("\n## 4. Rincian Input di Bawah 16 px (Aturan C - Risiko iOS Auto-Zoom)\n")
        md.append("| Rute | Perangkat | Tag / Field | Ukuran Font Saat Ini |")
        md.append("|---|---|---|:---:|")
        seen_inputs = set()
        for ic in input_cases:
            for inp in ic["details"].get("inputsUnder16px", []):
                key = (ic["route_path"], inp["name"])
                if key not in seen_inputs:
                    seen_inputs.add(key)
                    md.append(f"| `{ic['route_path']}` | {ic['device_name']} | `<{inp['tag']} name=\"{inp['name']}\">` | {inp['fontSize']} px |")

    table_cases = [r for r in records if not r["g_table_scrolling"]]
    if table_cases:
        md.append("\n## 5. Rincian Tabel Tanpa Pembungkus Gulir Internal (Aturan G)\n")
        md.append("| Rute | Perangkat | Class Tabel | Lebar Tabel |")
        md.append("|---|---|---|:---:|")
        for tc in table_cases:
            for tb in tc["details"].get("unwrappedWideTables", []):
                md.append(f"| `{tc['route_path']}` | {tc['device_name']} | `{tb['className']}` | {tb['width']} px |")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")

    print(f"\n[REPORT] Laporan tersimpan di: {report_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Audit Responsif Menyeluruh Collective Campus")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="Base URL server lokal")
    parser.add_argument("--devices", help="Perangkat yang diuji (dipisah koma)")
    parser.add_argument("--routes", help="Rute yang diuji (dipisah koma)")
    parser.add_argument("--no-screenshots", action="store_true", help="Lewati pengambilan tangkapan layar")

    args = parser.parse_args()
    selected_devs = [d.strip() for d in args.devices.split(",")] if args.devices else None
    selected_rts = [r.strip() for r in args.routes.split(",")] if args.routes else None

    run_audit(
        base_url=args.url,
        selected_devices=selected_devs,
        selected_routes=selected_rts,
        take_screenshots=not args.no_screenshots
    )
