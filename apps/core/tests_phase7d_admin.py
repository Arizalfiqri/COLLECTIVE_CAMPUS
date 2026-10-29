import datetime
from django.test import TestCase, Client
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.contrib.admin.sites import site as admin_site

from apps.accounts.models import Campus, StudentProfile
from apps.accounts.admin import CampusAdmin
from apps.catalog.models import Item, Category
from apps.rentals.models import Rental, Dispute
from apps.verification.models import KtmVerification
from apps.payments.models import WithdrawalRequest
from apps.payments.reconciliation import run_financial_reconciliation
from apps.trust.models import TrustTrainingExample, TrustModelVersion
from apps.core.services import get_staff_operational_stats

User = get_user_model()


class Phase7DAdminOperationalTests(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username='staff_test',
            email='staff@kampusrent.id',
            password='password123',
            full_name='Staf Pengelola',
            is_staff=True,
            is_superuser=True
        )
        self.regular_user = User.objects.create_user(
            username='student_test',
            email='student@kampus.ac.id',
            password='password123',
            full_name='Mahasiswa Biasa'
        )

        self.campus_active = Campus.objects.create(
            name='Institut Teknologi Sumatera',
            short_name='ITERA',
            city='Lampung Selatan',
            is_active=True
        )
        self.campus_inactive = Campus.objects.create(
            name='Kampus Nonaktif Test',
            short_name='NONAKTIF',
            city='Bandar Lampung',
            is_active=False
        )

        self.category = Category.objects.create(name='Kamera & Lensa', slug='kamera')
        self.item = Item.objects.create(
            owner=self.regular_user,
            category=self.category,
            title='Lensa Sony 50mm f/1.8',
            description='Lensa fix tajam',
            price_per_day=40000,
            deposit_amount=50000,
            estimated_value=1200000,
            is_active=True
        )

    def test_staff_navigation_links_no_404(self):
        """Memverifikasi seluruh 8 tautan operasional staf dapat dibuka tanpa 404."""
        client = Client()
        client.force_login(self.staff_user)

        staff_urls = [
            '/admin/',
            '/admin/verification/ktmverification/',
            '/admin/penarikan/',
            '/admin/rentals/dispute/',
            '/admin/rekonsiliasi/',
            '/admin/model-skor/',
            '/admin/ringkasan/',
            '/admin/pengumuman/',
            '/admin/rentals/rental/',
            '/admin/rentals/rental/?status__exact=menunggu_persetujuan',
        ]

        for url in staff_urls:
            with self.subTest(url=url):
                resp = client.get(url)
                self.assertNotEqual(
                    resp.status_code, 404,
                    f"URL operasional staf '{url}' menghasilkan galat 404!"
                )
                self.assertEqual(
                    resp.status_code, 200,
                    f"URL operasional staf '{url}' menghasilkan status {resp.status_code} (diharapkan 200)."
                )

    def test_non_staff_forbidden_on_staff_endpoints(self):
        """Memverifikasi pengguna non-staf atau anonim dilarang membuka endpoint operasional."""
        client = Client()
        
        protected_urls = [
            '/admin/penarikan/',
            '/admin/rekonsiliasi/',
            '/admin/model-skor/',
            '/admin/ringkasan/',
        ]

        # 1. Anonim dialihkan ke login
        for url in protected_urls:
            with self.subTest(user='anonymous', url=url):
                resp = client.get(url)
                self.assertEqual(resp.status_code, 302)

        # 2. Pengguna terotentikasi biasa ditolak (302 atau 403)
        client.force_login(self.regular_user)
        for url in protected_urls:
            with self.subTest(user='regular', url=url):
                resp = client.get(url)
                self.assertIn(resp.status_code, [302, 403])

    def test_operational_queue_counts(self):
        """Memverifikasi perhitungan 4 antrean operasional (KTM, penarikan, sengketa, sewa >48 jam)."""
        now = timezone.now()
        past_50h = now - datetime.timedelta(hours=50)

        # 1. KTM Menunggu
        KtmVerification.objects.create(
            user=self.regular_user,
            status=KtmVerification.Status.MENUNGGU
        )
        # 2. Penarikan Diminta
        w = WithdrawalRequest(
            user=self.regular_user,
            amount=50000,
            method=WithdrawalRequest.Method.BCA,
            account_name="Mahasiswa",
            status=WithdrawalRequest.Status.DIMINTA
        )
        w.set_account_number("1234567890")
        w.save()

        # 3. Sewa & Sengketa Terbuka
        rental_dispute = Rental.objects.create(
            code='KR-DS01',
            item=self.item,
            renter=self.regular_user,
            owner=self.staff_user,
            status=Rental.Status.SENGKETA,
            start_date=now.date(),
            end_date=(now + datetime.timedelta(days=1)).date(),
            days=1,
            price_per_day_snapshot=40000,
            rent_total=40000,
            deposit_total=50000,
            grand_total=90000
        )
        Dispute.objects.create(
            rental=rental_dispute,
            opened_by=self.staff_user,
            reason="Barang lecet",
            status=Dispute.Status.TERBUKA
        )

        # 4. Sewa Menunggu Konfirmasi > 48 jam
        r_stale = Rental.objects.create(
            code='KR-ST01',
            item=self.item,
            renter=self.regular_user,
            owner=self.staff_user,
            status=Rental.Status.MENUNGGU_PERSETUJUAN,
            start_date=now.date(),
            end_date=(now + datetime.timedelta(days=2)).date(),
            days=2,
            price_per_day_snapshot=40000,
            rent_total=80000,
            deposit_total=50000,
            grand_total=130000
        )
        Rental.objects.filter(pk=r_stale.pk).update(created_at=past_50h)

        # Hitung statistik
        stats = get_staff_operational_stats()
        self.assertEqual(stats['ktm_queue_count'], 1)
        self.assertEqual(stats['withdrawal_queue_count'], 1)
        self.assertEqual(stats['dispute_queue_count'], 1)
        self.assertEqual(stats['rental_stale_count'], 1)
        self.assertEqual(stats['total_queue'], 4)

        # Render halaman /admin/
        client = Client()
        client.force_login(self.staff_user)
        resp = client.get('/admin/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Pusat Operasional Platform")
        self.assertContains(resp, "4 Menunggu")

    def test_financial_cards_match_reconciliation(self):
        """Memverifikasi kartu keuangan di pusat operasional konsisten dengan rekonsiliasi."""
        stats = get_staff_operational_stats()
        recon = run_financial_reconciliation()

        self.assertEqual(stats['escrow_held'], recon['total_escrow_held'])
        self.assertEqual(stats['user_balances_total'], recon['total_user_wallets'])
        self.assertEqual(stats['platform_commission_total'], recon['total_commission'])
        self.assertEqual(stats['gotong_royong_fund'], recon['total_protection_fund'])
        self.assertEqual(stats['recon_balanced'], recon['summary']['global_balanced'])


    def test_campus_admin_actions_and_registration_suggestions(self):
        """Memverifikasi tindakan aktif/nonaktif kampus dan saran registrasi hanya kampus aktif."""
        # Uji saran registrasi
        client = Client()
        resp_reg = client.get('/daftar/')
        self.assertEqual(resp_reg.status_code, 200)
        # Kampus aktif muncul
        self.assertContains(resp_reg, "Institut Teknologi Sumatera")
        # Kampus nonaktif tidak muncul
        self.assertNotContains(resp_reg, "Kampus Nonaktif Test")

        # Uji tindakan admin nonaktifkan
        ca = CampusAdmin(Campus, admin_site)
        qs = Campus.objects.filter(pk=self.campus_active.pk)
        ca.nonaktifkan_kampus(None, qs)
        self.campus_active.refresh_from_db()
        self.assertFalse(self.campus_active.is_active)

        # Uji tindakan admin aktifkan
        ca.aktifkan_kampus(None, qs)
        self.campus_active.refresh_from_db()
        self.assertTrue(self.campus_active.is_active)

    def test_trust_models_registered_and_readonly(self):
        """Memverifikasi TrustTrainingExample dan TrustModelVersion terdaftar dan hanya-baca."""
        self.assertIn(TrustTrainingExample, admin_site._registry)
        self.assertIn(TrustModelVersion, admin_site._registry)

        example_admin = admin_site._registry[TrustTrainingExample]
        model_ver_admin = admin_site._registry[TrustModelVersion]

        # Wajib read-only
        self.assertFalse(example_admin.has_add_permission(None))
        self.assertFalse(example_admin.has_change_permission(None))
        self.assertFalse(example_admin.has_delete_permission(None))

        self.assertFalse(model_ver_admin.has_add_permission(None))
        self.assertFalse(model_ver_admin.has_change_permission(None))
        self.assertFalse(model_ver_admin.has_delete_permission(None))
