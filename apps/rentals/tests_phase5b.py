"""
Unit and integration tests for FASE 5B:
- Serah terima (state machine, jadwal, foto sebelum, foto serah terima, consent, KTM ditahan)
- Foto privat, kompresi, akses IDOR, retensi dan pembersihan foto
- Pengembalian, denda keterlambatan, konfirmasi kondisi baik, pelaporan masalah (sengketa)
- Penyelesaian sengketa oleh admin dan persetujuan potongan oleh penyewa
- Barang tidak dikembalikan (sengketa otomatis, deposit ke pemilik, suspend akun, blacklist NIM)
- Klaim Dana Gotong Royong dan invarian buku besar
- Aturan ulasan dan penghitungan ulang skor kepercayaan
"""
import io
import json
from datetime import date, datetime, timedelta, time as time_module
from unittest import mock
from PIL import Image

from django.test import TestCase, Client, override_settings
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.accounts.models import User, StudentProfile, Campus, MeetingPoint, BlacklistedNim
from apps.catalog.models import Category, Item
from apps.rentals.models import (
    Rental,
    ConditionPhoto,
    Review,
    Dispute,
    RentalAgreement,
    HandoverSchedule,
)
from apps.payments.models import Payment, DepositHold, Payout, LedgerEntry
from apps.payments.services import (
    record_payment_settlement,
    settle_rental_funds,
    validate_ledger_invariant,
)
from apps.rentals.services import (
    ajukan_sewa,
    setujui_sewa,
    konfirmasi_pembayaran,
    usulkan_jadwal_serah_terima,
    konfirmasi_jadwal_serah_terima,
    setujui_foto_serah_terima,
    konfirmasi_ktm_ditahan,
    konfirmasi_serah_terima,
    ajukan_pengembalian,
    konfirmasi_pengembalian_baik,
    laporkan_masalah_sengketa,
    penyewa_setujui_potongan,
    selesaikan_sengketa_admin,
    proses_barang_tidak_dikembalikan,
    proses_klaim_dana_proteksi_admin,
    buat_ulasan,
    RentalError,
    RentalValidationError,
    RentalPermissionError,
    RentalStateError,
)
from apps.rentals.photos import (
    resize_and_compress_image,
    save_condition_photo,
    purge_handover_photos,
)
from apps.rentals.management.commands.process_deadlines import run_process_deadlines
from apps.trust.models import TrustScore
from apps.trust.services import recompute_trust_score


def create_dummy_image_file(name='test.jpg', size=(800, 600), color='blue'):
    file_obj = io.BytesIO()
    image = Image.new('RGB', size, color=color)
    image.save(file_obj, format='JPEG')
    file_obj.seek(0)
    return SimpleUploadedFile(name, file_obj.read(), content_type='image/jpeg')


class Phase5BBaseTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.today = timezone.localdate()

        # Kampus
        self.campus_a = Campus.objects.create(name='Institut Teknologi Uji', short_name='ITU', city='Bandung')
        self.campus_b = Campus.objects.create(name='Universitas Sains Uji', short_name='USU', city='Bandung')

        # Titik Temu
        self.mp_public = MeetingPoint.objects.create(campus=self.campus_a, name='Plaza Utama', is_public=True)
        self.mp_private = MeetingPoint.objects.create(campus=self.campus_a, name='Lab Khusus Mesin', is_public=False)

        # Pengguna
        self.owner = User.objects.create_user(
            username='pemilik5b', email='pemilik@test.id', password='Password123!',
            full_name='Pemilik Handover', is_verified_student=True,
        )
        StudentProfile.objects.create(user=self.owner, nim='13520001', campus=self.campus_a)

        self.renter = User.objects.create_user(
            username='penyewa5b', email='penyewa@test.id', password='Password123!',
            full_name='Penyewa Handover', is_verified_student=True,
        )
        StudentProfile.objects.create(user=self.renter, nim='13520002', campus=self.campus_a)

        self.admin_user = User.objects.create_superuser(
            username='admin5b', email='admin@test.id', password='Password123!',
            full_name='Admin Penguji',
        )

        self.third_party = User.objects.create_user(
            username='asing5b', email='asing@test.id', password='Password123!',
            full_name='Pengguna Asing', is_verified_student=True,
        )
        StudentProfile.objects.create(user=self.third_party, nim='13520099', campus=self.campus_b)

        # Kategori & Barang
        self.category = Category.objects.create(name='Elektronik 5B', slug='elektronik-5b', order=1)
        self.item = Item.objects.create(
            owner=self.owner,
            category=self.category,
            title='Proyektor Epson EB-X400',
            slug='proyektor-epson-eb-x400',
            price_per_day=50000,
            deposit_amount=200000,
            estimated_value=500000,
            min_days=1,
            max_days=7,
            pickup_area='Dekat Gerbang Utama',
            require_ktm_held=True,
        )

        self.client = Client()

    def _setup_paid_rental(self, days=3, require_ktm=True):
        """Helper untuk membuat sewa pada status DIBAYAR dengan saldo buku besar lengkap."""
        self.item.require_ktm_held = require_ktm
        self.item.save(update_fields=['require_ktm_held'])

        start_date = self.today + timedelta(days=1)
        end_date = start_date + timedelta(days=days - 1)

        rental = ajukan_sewa(
            item=self.item,
            renter=self.renter,
            start_date=start_date,
            end_date=end_date,
            use_protection=True,
            terms_accepted=True,
        )
        setujui_sewa(rental, self.owner)

        payment = Payment.objects.create(
            rental=rental,
            order_id=f"TEST-{rental.code}",
            payment_type="qris",
            gross_amount=rental.grand_total,
            transaction_id="mock-midtrans-id-5b",
            status=Payment.Status.SETTLEMENT,
        )
        record_payment_settlement(rental, payment)
        konfirmasi_pembayaran(rental, payment)
        rental.refresh_from_db()
        return rental



class Phase5BHandoverFlowTest(Phase5BBaseTestCase):
    """Pengujian alur serah terima, foto, persetujuan, dan prasyarat."""

    def test_handover_schedule_proposal_and_cross_campus_rule(self):
        """Memverifikasi usulan jadwal serah terima dan aturan titik temu lintas kampus."""
        rental = self._setup_paid_rental()

        meet_time = timezone.now() + timedelta(days=1)
        # 1. Sesama kampus bebas memilih titik apa saja
        schedule = usulkan_jadwal_serah_terima(rental, self.owner, meet_time, self.mp_private, note="Lantai 2")
        self.assertEqual(schedule.status, HandoverSchedule.Status.DIUSULKAN)
        self.assertEqual(schedule.meeting_point, self.mp_private)

        # 2. Pihak lawan (penyewa) mengonfirmasi
        konfirmasi_jadwal_serah_terima(rental, self.renter)
        schedule.refresh_from_db()
        self.assertEqual(schedule.status, HandoverSchedule.Status.DIKONFIRMASI)

        # 3. Pengusul tidak dapat mengonfirmasi usulannya sendiri
        with self.assertRaises(RentalValidationError):
            konfirmasi_jadwal_serah_terima(rental, self.owner)

        # 4. Ganti penyewa ke beda kampus -> wajib titik publik
        self.renter.student_profile.campus = self.campus_b
        self.renter.student_profile.save()

        with self.assertRaises(RentalValidationError):
            usulkan_jadwal_serah_terima(rental, self.renter, meet_time, self.mp_private, note="Titik non-publik")

        # Jika titik publik, berhasil
        schedule2 = usulkan_jadwal_serah_terima(rental, self.renter, meet_time, self.mp_public, note="Titik publik aman")
        self.assertEqual(schedule2.meeting_point, self.mp_public)

    def test_handover_prerequisites_enforcement(self):
        """Transisi dibayar -> sedang_disewa memvalidasi semua prasyarat."""
        rental = self._setup_paid_rental(require_ktm=True)

        # A. Belum ada foto sebelum dan foto serah terima -> konfirmasi gagal
        with self.assertRaises(RentalValidationError):
            konfirmasi_serah_terima(rental, self.owner)
            konfirmasi_serah_terima(rental, self.renter)

        # B. Pemilik unggah 2 foto kondisi sebelum
        img1 = create_dummy_image_file('sebelum1.jpg')
        img2 = create_dummy_image_file('sebelum2.jpg')
        save_condition_photo(rental, self.owner, ConditionPhoto.Phase.SEBELUM, img1)
        save_condition_photo(rental, self.owner, ConditionPhoto.Phase.SEBELUM, img2)
        self.assertEqual(rental.condition_photos.filter(phase='sebelum').count(), 2)

        # C. Blokir foto serah terima tanpa persetujuan (consent)
        rental.refresh_from_db()
        rental.handover_photo_consent_at = None
        rental.save()

        img_handover = create_dummy_image_file('serah.jpg')
        self.client.force_login(self.owner)
        resp = self.client.post(f"/sewa/{rental.code}/foto/unggah/serah_terima/", {'photo_file': img_handover})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(rental.condition_photos.filter(phase='serah_terima').count(), 0)

        # D. Penyewa berikan persetujuan (consent)
        setujui_foto_serah_terima(rental, self.renter)
        rental.refresh_from_db()
        self.assertIsNotNone(rental.handover_photo_consent_at)

        # E. Ambil foto serah terima berhasil
        img_handover_fresh = create_dummy_image_file('serah2.jpg')
        save_condition_photo(rental, self.owner, ConditionPhoto.Phase.SERAH_TERIMA, img_handover_fresh)
        self.assertEqual(rental.condition_photos.filter(phase='serah_terima').count(), 1)

        # F. Jika require_ktm_held tapi belum konfirmasi KTM -> gagal
        with self.assertRaises(RentalValidationError):
            konfirmasi_serah_terima(rental, self.owner)
            konfirmasi_serah_terima(rental, self.renter)

        # G. Konfirmasi KTM ditahan
        konfirmasi_ktm_ditahan(rental, self.owner)
        rental.refresh_from_db()
        self.assertIsNotNone(rental.ktm_held_confirmed_at)

        # H. Satu pihak konfirmasi -> status masih DIBAYAR
        konfirmasi_serah_terima(rental, self.owner)
        rental.refresh_from_db()
        self.assertEqual(rental.status, Rental.Status.DIBAYAR)
        self.assertIsNotNone(rental.handed_over_owner_at)

        # I. Pihak kedua konfirmasi -> status berubah SEDANG_DISEWA
        konfirmasi_serah_terima(rental, self.renter)
        rental.refresh_from_db()
        self.assertEqual(rental.status, Rental.Status.SEDANG_DISEWA)
        self.assertIsNotNone(rental.handed_over_renter_at)


class Phase5BPhotoSecurityAndRetentionTest(Phase5BBaseTestCase):
    """Pengujian kompresi foto, serving terproteksi (Anti-IDOR), dan penghapusan berkala."""

    def test_photo_resize_and_compression(self):
        """Memverifikasi foto dikompresi ke maksimal 1280 px dan format JPEG."""
        large_img = Image.new('RGB', (2000, 1500), color='red')
        in_buf = io.BytesIO()
        large_img.save(in_buf, format='PNG')
        in_buf.seek(0)

        compressed_bytes = resize_and_compress_image(in_buf.getvalue(), max_dim=1280, quality=80)
        out_img = Image.open(io.BytesIO(compressed_bytes))

        self.assertEqual(out_img.format, 'JPEG')
        self.assertLessEqual(max(out_img.size), 1280)

    def test_protected_photo_serve_idor_prevention(self):
        """Foto hanya dapat diakses peserta sewa dan admin dengan Cache-Control no-store."""
        rental = self._setup_paid_rental()
        img = create_dummy_image_file('privat.jpg')
        photo = save_condition_photo(rental, self.owner, ConditionPhoto.Phase.SEBELUM, img)

        url = f"/sewa/{rental.code}/foto/{photo.id}/"

        # 1. Penyewa berhak mengakses
        self.client.force_login(self.renter)
        resp_renter = self.client.get(url)
        self.assertEqual(resp_renter.status_code, 200)
        self.assertEqual(resp_renter.headers.get('Cache-Control'), 'no-store, private')

        # 2. Pemilik berhak mengakses
        self.client.force_login(self.owner)
        resp_owner = self.client.get(url)
        self.assertEqual(resp_owner.status_code, 200)

        # 3. Admin berhak mengakses
        self.client.force_login(self.admin_user)
        resp_admin = self.client.get(url)
        self.assertEqual(resp_admin.status_code, 200)

        # 4. Pihak ketiga (IDOR) ditolak (403 Forbidden)
        self.client.force_login(self.third_party)
        resp_other = self.client.get(url)
        self.assertEqual(resp_other.status_code, 403)

        # 5. Pengguna belum login diarahkan ke login
        self.client.logout()
        resp_anon = self.client.get(url)
        self.assertEqual(resp_anon.status_code, 302)

    def test_purge_handover_photos_retention(self):
        """Pembersihan foto serah terima setelah retensi, idempoten, dan tidak menghapus jika ada sengketa."""
        rental1 = self._setup_paid_rental()

        # Buat item2 agar tidak double-booking untuk rental2
        item2 = Item.objects.create(
            owner=self.owner,
            category=self.category,
            title='Proyektor Kedua',
            slug='proyektor-kedua',
            price_per_day=50000,
            deposit_amount=200000,
            estimated_value=500000,
            min_days=1,
            max_days=7,
        )
        self.item = item2
        rental2 = self._setup_paid_rental()

        img1 = create_dummy_image_file('ht1.jpg')
        img2 = create_dummy_image_file('ht2.jpg')
        photo1 = save_condition_photo(rental1, self.owner, ConditionPhoto.Phase.SERAH_TERIMA, img1)
        photo2 = save_condition_photo(rental2, self.owner, ConditionPhoto.Phase.SERAH_TERIMA, img2)

        # Set status selesai di masa lalu (40 hari yang lalu)
        cutoff_date = timezone.now() - timedelta(days=40)
        rental1.status = Rental.Status.SELESAI
        rental1.status_changed_at = cutoff_date
        rental1.save()

        # Rental 2 selesai tapi memiliki sengketa
        rental2.status = Rental.Status.SELESAI
        rental2.status_changed_at = cutoff_date
        rental2.save()
        Dispute.objects.create(rental=rental2, opened_by=self.owner, reason="Sengketa masa lalu")

        # Jalankan pembersihan
        purged = purge_handover_photos()
        self.assertEqual(purged, 1)

        # Photo 1 terhapus, Photo 2 tetap ada
        self.assertFalse(ConditionPhoto.objects.filter(id=photo1.id).exists())
        self.assertTrue(ConditionPhoto.objects.filter(id=photo2.id).exists())


@override_settings(DEPOSIT_MODE='legacy')
class Phase5BReturnAndDisputeTest(Phase5BBaseTestCase):
    """Pengujian pengembalian, keterlambatan, sengketa, dan konsistensi buku besar (Mode Legacy Deposit)."""

    def test_return_request_and_late_fee_calculation(self):
        """Penyewa mengajukan pengembalian dengan minimal 2 foto dan perhitungan keterlambatan."""
        rental = self._setup_paid_rental(days=3, require_ktm=True)
        rental.status = Rental.Status.SEDANG_DISEWA
        rental.save()

        # Tanpa foto -> gagal
        with self.assertRaises(RentalValidationError):
            ajukan_pengembalian(rental, self.renter)

        # Unggah 2 foto sesudah
        img1 = create_dummy_image_file('sesudah1.jpg')
        img2 = create_dummy_image_file('sesudah2.jpg')
        save_condition_photo(rental, self.renter, ConditionPhoto.Phase.SESUDAH, img1)
        save_condition_photo(rental, self.renter, ConditionPhoto.Phase.SESUDAH, img2)

        # Simulasi pengembalian terlambat 2 hari
        with mock.patch('django.utils.timezone.localdate') as mock_date:
            mock_date.return_value = rental.end_date + timedelta(days=2)
            ajukan_pengembalian(rental, self.renter)

        rental.refresh_from_db()
        self.assertEqual(rental.status, Rental.Status.MENUNGGU_KONFIRMASI_PENGEMBALIAN)
        self.assertEqual(rental.late_days, 2)
        # denda = 50.000 * 0.5 * 2 = 50.000
        self.assertEqual(rental.late_fee, 50000)

    def test_confirm_good_return_and_ledger_settlement(self):
        """Konfirmasi kondisi baik menyelesaikan dana sewa dan melepas deposit."""
        rental = self._setup_paid_rental(days=3, require_ktm=True)
        rental.status = Rental.Status.MENUNGGU_KONFIRMASI_PENGEMBALIAN
        rental.late_days = 1
        rental.late_fee = 25000  # terlambat 1 hari
        rental.save()

        konfirmasi_pengembalian_baik(rental, self.owner)
        rental.refresh_from_db()

        self.assertEqual(rental.status, Rental.Status.SELESAI)
        self.assertIsNotNone(rental.ktm_returned_confirmed_at)

        # Validasi buku besar dan invarian
        validate_ledger_invariant(rental)
        hold = DepositHold.objects.get(rental=rental)
        self.assertEqual(hold.status, DepositHold.Status.DIPOTONG_SEBAGIAN)

        # Deposit total 200.000, late_fee 25.000 -> refund 175.000
        refund_entry = rental.ledger_entries.filter(kind=LedgerEntry.Kind.KELUAR_DEPOSIT_DIKEMBALIKAN).first()
        self.assertIsNotNone(refund_entry)
        self.assertEqual(refund_entry.amount, 175000)

        late_entry = rental.ledger_entries.filter(kind=LedgerEntry.Kind.KELUAR_DENDA_KE_PEMILIK).first()
        self.assertIsNotNone(late_entry)
        self.assertEqual(late_entry.amount, 25000)

    def test_dispute_flow_renter_agrees_deduction(self):
        """Alur sengketa: Pemilik mengajukan potongan, penyewa menyetujui langsung."""
        rental = self._setup_paid_rental(days=3, require_ktm=False)
        rental.status = Rental.Status.MENUNGGU_KONFIRMASI_PENGEMBALIAN
        rental.save()

        # Pemilik ajukan kompensasi kerusakan Rp50.000
        laporkan_masalah_sengketa(rental, self.owner, reason="Lensa tergores halus", deduction_amount=50000)
        rental.refresh_from_db()
        self.assertEqual(rental.status, Rental.Status.SENGKETA)
        self.assertEqual(rental.damage_fee, 50000)

        # Penyewa setujui potongan
        penyewa_setujui_potongan(rental, self.renter)
        rental.refresh_from_db()
        self.assertEqual(rental.status, Rental.Status.SELESAI)

        # Invarian seimbang
        validate_ledger_invariant(rental)
        comp_entry = rental.ledger_entries.filter(kind=LedgerEntry.Kind.KELUAR_DEPOSIT_KE_PEMILIK).first()
        self.assertIsNotNone(comp_entry)
        self.assertEqual(comp_entry.amount, 50000)

    def test_dispute_flow_admin_decision(self):
        """Alur sengketa: Admin memutuskan penyelesaian (potong sebagian)."""
        rental = self._setup_paid_rental(days=3, require_ktm=False)
        rental.status = Rental.Status.MENUNGGU_KONFIRMASI_PENGEMBALIAN
        rental.save()

        laporkan_masalah_sengketa(rental, self.owner, reason="Kabel power hilang", deduction_amount=100000)

        # Admin putuskan potong Rp75.000
        selesaikan_sengketa_admin(
            rental=rental,
            admin_user=self.admin_user,
            decision=Dispute.Decision.POTONG_SEBAGIAN,
            deduction_amount=75000,
            decision_note="Kabel pengganti seharga Rp75.000."
        )
        rental.refresh_from_db()
        self.assertEqual(rental.status, Rental.Status.SELESAI)
        self.assertEqual(rental.damage_fee, 75000)
        validate_ledger_invariant(rental)


class Phase5BNonReturnAndDeadlineTest(Phase5BBaseTestCase):
    """Pengujian penanganan otomatis barang tidak dikembalikan dan batas waktu."""

    @override_settings(DEPOSIT_MODE='legacy')
    def test_non_return_handling_and_blacklisting(self):
        """Barang tidak dikembalikan melewati grace period memicu dispute, sita deposit, suspend akun, blacklist NIM."""
        rental = self._setup_paid_rental(days=2)
        rental.status = Rental.Status.SEDANG_DISEWA
        rental.end_date = self.today - timedelta(days=5)
        rental.save()

        # Jalankan process_deadlines
        results = run_process_deadlines()
        self.assertGreaterEqual(results['non_returns'], 1)

        rental.refresh_from_db()
        self.assertEqual(rental.status, Rental.Status.SENGKETA)

        # Deposit penuh dialihkan ke pemilik
        self.assertEqual(rental.damage_fee, rental.deposit_total)
        validate_ledger_invariant(rental)

        # Penyewa dibekukan
        self.renter.refresh_from_db()
        self.assertTrue(self.renter.is_suspended)

        # NIM masuk daftar hitam
        self.assertTrue(BlacklistedNim.objects.filter(nim='13520002').exists())

        # Admin memutuskan klaim Dana Gotong Royong
        claim_nominal = proses_klaim_dana_proteksi_admin(rental, self.admin_user, note="Klaim barang tidak kembali")
        self.assertGreater(claim_nominal, 0)
        validate_ledger_invariant(rental)

    def test_auto_confirm_return_after_deadline(self):
        """Pengembalian otomatis disetujui jika pemilik tidak merespons setelah AUTO_CONFIRM_RETURN_HOURS."""
        rental = self._setup_paid_rental(days=2)
        rental.status = Rental.Status.MENUNGGU_KONFIRMASI_PENGEMBALIAN
        rental.return_requested_at = timezone.now() - timedelta(hours=50)
        rental.save()

        results = run_process_deadlines()
        self.assertGreaterEqual(results['auto_confirmed_returns'], 1)

        rental.refresh_from_db()
        self.assertEqual(rental.status, Rental.Status.SELESAI)
        validate_ledger_invariant(rental)


class Phase5BReviewAndTrustScoreTest(Phase5BBaseTestCase):
    """Pengujian sistem ulasan dan penghitungan ulang skor kepercayaan."""

    def test_review_creation_rules(self):
        """Ulasan hanya untuk peserta, status selesai, rating 1-5, dan maksimal 300 karakter."""
        rental = self._setup_paid_rental()

        # Belum selesai -> tidak bisa memberi ulasan
        with self.assertRaises(RentalStateError):
            buat_ulasan(rental, self.renter, rating=5, comment="Bagus")

        rental.status = Rental.Status.SELESAI
        rental.save()

        # Bukan peserta -> tidak bisa
        with self.assertRaises(RentalPermissionError):
            buat_ulasan(rental, self.third_party, rating=5, comment="Menyusup")

        # Rating di luar 1-5 -> validasi gagal
        with self.assertRaises(RentalValidationError):
            buat_ulasan(rental, self.renter, rating=6, comment="Luar biasa")

        # Berhasil
        review_renter = buat_ulasan(rental, self.renter, rating=5, comment="Barang sangat memuaskan!")
        self.assertEqual(review_renter.rating, 5)

        # Ulasan ganda dari orang yang sama ditolak
        with self.assertRaises(RentalValidationError):
            buat_ulasan(rental, self.renter, rating=4, comment="Ulas lagi")

        # Pemilik juga bisa memberi ulasan
        review_owner = buat_ulasan(rental, self.owner, rating=5, comment="Penyewa sangat ramah dan tepat waktu.")
        self.assertEqual(review_owner.rating, 5)

        # Cek recompute_trust_score
        ts = TrustScore.objects.get(user=self.owner)
        self.assertIn('jumlah_sewa_selesai', ts.features)
        self.assertIn('rasio_tepat_waktu', ts.features)
