import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from django.contrib.auth import get_user_model
from django.contrib.sessions.backends.db import SessionStore
from playwright.sync_api import sync_playwright
from apps.catalog.models import Item
from apps.rentals.models import Rental
from apps.chat.models import Conversation

User = get_user_model()
student = User.objects.filter(is_staff=False, student_profile__isnull=False).first() or User.objects.filter(is_staff=False).first()
staff = User.objects.filter(is_staff=True).first()

def get_session(u):
    if not u: return None
    s = SessionStore()
    s['_auth_user_id'] = str(u.pk)
    s['_auth_user_backend'] = 'django.contrib.auth.backends.ModelBackend'
    s['_auth_user_hash'] = u.get_session_auth_hash()
    s.save()
    return s.session_key

student_sess = get_session(student)
staff_sess = get_session(staff)

routes = [
    ('/', 'public', None),
    ('/barang/', 'public', None),
    ('/tentang/', 'public', None),
    ('/bantuan/', 'public', None),
    ('/syarat-ketentuan/', 'public', None),
    ('/kebijakan-privasi/', 'public', None),
    ('/panduan-komunitas/', 'public', None),
    ('/kontak/', 'public', None),
    ('/masuk/', 'public', None),
    ('/daftar/', 'public', None),
    ('/dashboard/?tab=ringkasan', 'user', student_sess),
    ('/dashboard/?tab=sewa_saya', 'user', student_sess),
    ('/dashboard/?tab=barang_saya', 'user', student_sess),
    ('/verifikasi-ktm/', 'user', student_sess),
    ('/barang/baru/', 'user', student_sess),
    ('/barang/saya/', 'user', student_sess),
    ('/dompet/', 'user', student_sess),
    ('/dompet/tarik/', 'user', student_sess),
    ('/pesan/', 'user', student_sess),
    ('/admin/', 'admin', staff_sess),
    ('/admin/rekonsiliasi/', 'admin', staff_sess),
    ('/admin/penarikan/', 'admin', staff_sess),
    ('/admin/ringkasan/', 'admin', staff_sess),
]

item = Item.objects.first()
if item:
    routes.append((f'/barang/{item.slug}/', 'public', None))
    routes.append((f'/barang/{item.slug}/ubah/', 'user', get_session(item.owner)))

conv = Conversation.objects.first()
if conv:
    routes.append((f'/pesan/{conv.id}/', 'user', get_session(conv.renter)))

rental = Rental.objects.first()
if rental:
    routes.append((f'/sewa/{rental.code}/', 'user', get_session(rental.renter)))
    routes.append((f'/sewa/{rental.code}/perjanjian/', 'user', get_session(rental.renter)))

print(f"Testing {len(routes)} routes on 360x800...")

with sync_playwright() as p:
    browser = p.chromium.launch()
    for path, role, sess in routes:
        ctx = browser.new_context(viewport={'width': 360, 'height': 800})
        if sess:
            ctx.add_cookies([{'name': 'sessionid', 'value': sess, 'domain': '127.0.0.1', 'path': '/'}])
        page = ctx.new_page()
        try:
            page.goto(f'http://127.0.0.1:8000{path}', timeout=10000)
            page.wait_for_load_state('domcontentloaded')
            page.wait_for_timeout(200)
            
            overflow = page.evaluate('''() => {
                const docW = document.documentElement.scrollWidth;
                const bodyW = document.body.scrollWidth;
                const winW = window.innerWidth;
                
                // Find offending elements
                let offenders = [];
                document.querySelectorAll('*').forEach(el => {
                    const rect = el.getBoundingClientRect();
                    if (rect.right > winW + 1 && el.offsetWidth > 0) {
                        const tag = el.tagName.toLowerCase();
                        const cls = (el.className && typeof el.className === 'string') ? el.className.split(' ').slice(0, 3).join('.') : '';
                        offenders.push({ tag, cls, right: Math.round(rect.right), w: Math.round(rect.width) });
                    }
                });
                
                return {
                    docW, bodyW, winW,
                    hasOverflow: docW > winW || bodyW > winW,
                    offenders: offenders.slice(0, 3)
                };
            }''')
            
            status = 'OVERFLOW' if overflow['hasOverflow'] else 'OK'
            print(f"[{status:8}] {path:<40} (doc: {overflow['docW']}px, body: {overflow['bodyW']}px)")
            if overflow['hasOverflow'] and overflow['offenders']:
                print(f"          Offenders: {overflow['offenders']}")
        except Exception as e:
            print(f"[ERROR   ] {path}: {e}")
        finally:
            ctx.close()
    browser.close()
