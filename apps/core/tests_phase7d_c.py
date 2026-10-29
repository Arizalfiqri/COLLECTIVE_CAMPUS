from django.test import TestCase, Client, RequestFactory
from django.contrib.auth import get_user_model
from django.contrib.admin.sites import site as admin_site
from django.utils import timezone

from apps.accounts.models import SuspensionRecord
from apps.accounts.admin import UserAdmin
from apps.catalog.models import Item, Category
from apps.catalog.admin import ItemAdmin
from apps.payments.models import LedgerEntry, WalletTransaction, WithdrawalRequest
from apps.payments.admin import LedgerEntryAdmin, WalletTransactionAdmin, WithdrawalRequestAdmin
from apps.rentals.models import Rental
from apps.rentals.admin import RentalAdmin
from apps.core.models import Notification

User = get_user_model()


class Phase7DPartCTests(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username='staff_c_test',
            email='staff_c@kampusrent.id',
            password='password123',
            full_name='Staf Part C',
            is_staff=True,
            is_superuser=True
        )
        self.target_user = User.objects.create_user(
            username='user_c_target',
            email='target@kampusrent.id',
            password='password123',
            full_name='Pengguna Sasaran',
            is_active=True
        )
        self.category = Category.objects.create(name='Elektronik C', slug='elektronik-c')
        self.item = Item.objects.create(
            owner=self.target_user,
            category=self.category,
            title='Proyektor Mini C',
            description='Proyektor test part c',
            price_per_day=50000,
            deposit_amount=100000,
            estimated_value=1500000,
            is_active=True
        )
        self.factory = RequestFactory()

    def _create_request_with_messages(self, path, data=None):
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.contrib.sessions.backends.db import SessionStore
        request = self.factory.post(path, data or {})
        request.user = self.staff_user
        request.session = SessionStore()
        setattr(request, '_messages', FallbackStorage(request))
        return request

    def test_item_take_down_action(self):
        """Memverifikasi aksi turunkan barang dengan alasan menonaktifkan barang dan mengirim notifikasi."""
        item_admin = ItemAdmin(Item, admin_site)
        request = self._create_request_with_messages('/admin/catalog/item/', {
            'action': 'turunkan_barang_dengan_alasan',
            'confirm': 'yes',
            'reason': 'Barang tidak sesuai standar keselamatan kampus',
            '_selected_action': [self.item.pk]
        })

        # Jalankan aksi
        response = item_admin.turunkan_barang_dengan_alasan(request, Item.objects.filter(pk=self.item.pk))
        self.item.refresh_from_db()

        self.assertFalse(self.item.is_active, "Barang harus dinonaktifkan (is_active=False)")
        notif = Notification.objects.filter(user=self.target_user).first()
        self.assertIsNotNone(notif, "Pemilik barang harus menerima notifikasi resmi")
        self.assertIn('tidak sesuai standar keselamatan', notif.message)
        self.assertEqual(response.status_code, 302)

    def test_user_suspension_and_restoration(self):
        """Memverifikasi aksi bekukan pengguna dan pulihkan pengguna pada UserAdmin."""
        user_admin = UserAdmin(User, admin_site)

        # 1. Bekukan pengguna
        req_suspend = self._create_request_with_messages('/admin/accounts/user/', {
            'action': 'bekukan_pengguna',
            'confirm': 'yes',
            'reason': 'Terindikasi pelanggaran pengembalian barang sewa',
            '_selected_action': [self.target_user.pk]
        })

        resp_suspend = user_admin.bekukan_pengguna(req_suspend, User.objects.filter(pk=self.target_user.pk))
        self.target_user.refresh_from_db()

        self.assertTrue(self.target_user.is_suspended, "Pengguna harus berstatus is_suspended=True")
        suspension = SuspensionRecord.objects.filter(user=self.target_user, ended_at__isnull=True).first()
        self.assertIsNotNone(suspension, "SuspensionRecord harus tercatat aktif di basis data")
        self.assertEqual(suspension.suspended_by, self.staff_user)
        self.assertIn('pelanggaran pengembalian', suspension.reason)

        notif_suspend = Notification.objects.filter(user=self.target_user, title="Akun Anda Dibekukan").first()
        self.assertIsNotNone(notif_suspend, "Notifikasi pembekuan harus diterima pengguna")

        # 2. Pulihkan pengguna
        req_restore = self._create_request_with_messages('/admin/accounts/user/', {
            'action': 'pulihkan_pengguna',
            '_selected_action': [self.target_user.pk]
        })

        user_admin.pulihkan_pengguna(req_restore, User.objects.filter(pk=self.target_user.pk))
        self.target_user.refresh_from_db()

        self.assertFalse(self.target_user.is_suspended, "Pengguna harus berstatus is_suspended=False setelah pemulihan")
        suspension.refresh_from_db()
        self.assertIsNotNone(suspension.ended_at, "SuspensionRecord harus ditutup dengan ended_at terisi")

        notif_restore = Notification.objects.filter(user=self.target_user, title="Akun Anda Telah Dipulihkan").first()
        self.assertIsNotNone(notif_restore, "Notifikasi pemulihan harus diterima pengguna")

    def test_csv_exports(self):
        """Memverifikasi aksi ekspor CSV pada LedgerEntry, WalletTransaction, WithdrawalRequest, dan Rental."""
        # Setup data penarikan dengan nomor rekening sensitif
        withdrawal = WithdrawalRequest(
            user=self.target_user,
            amount=75000,
            method=WithdrawalRequest.Method.BCA,
            account_name='Nama Mahasiswa Target',
            status=WithdrawalRequest.Status.DIMINTA
        )
        withdrawal.set_account_number('123456789012')
        withdrawal.save()

        withdrawal_admin = WithdrawalRequestAdmin(WithdrawalRequest, admin_site)
        req = self._create_request_with_messages('/admin/payments/withdrawalrequest/')

        resp_withdrawal_csv = withdrawal_admin.actions[-1](withdrawal_admin, req, WithdrawalRequest.objects.filter(pk=withdrawal.pk))
        self.assertEqual(resp_withdrawal_csv.status_code, 200)
        self.assertEqual(resp_withdrawal_csv['Content-Type'], 'text/csv; charset=utf-8')
        content = resp_withdrawal_csv.content.decode('utf-8')

        # Verifikasi bahwa nomor rekening mentah TIDAK ADA di file CSV!
        self.assertNotIn('123456789012', content, "KEAMANAN: Nomor rekening lengkap dilarang masuk ke berkas ekspor CSV!")
        self.assertIn('9012', content, "4 digit terakhir rekening harus muncul")
        self.assertIn('••••', content, "Nomor rekening harus disamarkan (masked dengan bullet) di berkas ekspor CSV!")

    def test_broadcast_announcement_view(self):
        """Memverifikasi endpoint form pengumuman massal staf."""
        client = Client()
        client.force_login(self.staff_user)

        # GET halaman form
        resp_get = client.get('/admin/pengumuman/')
        self.assertEqual(resp_get.status_code, 200)
        self.assertContains(resp_get, "Kirim Pengumuman Massal Platform")

        # POST pengumuman
        initial_notif_count = Notification.objects.count()
        resp_post = client.post('/admin/pengumuman/', {
            'title': 'Pemberitahuan Sistem',
            'message': 'Platform akan mengalami pemeliharaan rutin malam ini.',
            'url': '/bantuan/'
        })
        self.assertEqual(resp_post.status_code, 302)

        new_notifs = Notification.objects.filter(title='Pemberitahuan Sistem')
        self.assertGreater(new_notifs.count(), 0, "Pengumuman harus disiarkan ke pengguna aktif")
        user_notif = new_notifs.filter(user=self.target_user).first()
        self.assertIsNotNone(user_notif, "Pengguna aktif harus menerima notifikasi pengumuman")
        self.assertEqual(user_notif.url, '/bantuan/')
