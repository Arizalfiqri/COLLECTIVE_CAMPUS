import io
from datetime import date, timedelta
from PIL import Image

from django.test import TestCase, Client, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.accounts.models import User, StudentProfile, Campus
from apps.catalog.forms import ItemForm
from apps.catalog.models import Category, Item, ItemPhoto
from apps.catalog.services import calculate_min_deposit, calculate_rental_summary, is_item_available
from apps.rentals.models import Rental
from apps.trust.models import TrustScore


class CatalogServicesAndRulesTest(TestCase):
    def setUp(self):
        # Pengguna terverifikasi 1 (Pemilik)
        self.owner = User.objects.create_user(
            username='pemilik_test', email='pemilik@test.id', password='Password123!',
            full_name='Pemilik Barang', is_verified_student=True
        )
        StudentProfile.objects.create(
            user=self.owner, nim='20210001', campus_name='Univ KampusRent', major='Informatika'
        )

        # Pengguna terverifikasi 2 (Penyewa)
        self.renter = User.objects.create_user(
            username='penyewa_test', email='penyewa@test.id', password='Password123!',
            full_name='Penyewa Mahasiswa', is_verified_student=True
        )
        StudentProfile.objects.create(
            user=self.renter, nim='20210002', campus_name='Univ KampusRent', major='Elektro'
        )

        # Pengguna belum terverifikasi
        self.unverified_user = User.objects.create_user(
            username='unverified_test', email='unverified@test.id', password='Password123!',
            full_name='Pengguna Baru', is_verified_student=False
        )

        # Kategori
        self.category_kamera = Category.objects.create(name='Kamera & Lensa', slug='kamera', order=1)
        self.category_laptop = Category.objects.create(name='Laptop & Aksesori', slug='laptop', order=2)

        # Item Kamera (Sesuai PROJECT_SPEC.md 7.2)
        self.item_kamera = Item.objects.create(
            owner=self.owner,
            category=self.category_kamera,
            title='Canon EOS M50 Mark II',
            description='Kamera mirrorless kondisi mulus lengkap lensa kit.',
            condition=Item.Condition.SANGAT_BAIK,
            estimated_value=8000000,
            price_per_day=75000,
            deposit_amount=500000,
            min_days=1,
            max_days=7,
            pickup_area='Gedung Sains & Seni',
            is_active=True
        )

    @override_settings(DEPOSIT_MODE='legacy')
    def test_min_deposit_calculation(self):
        """Uji aturan deposit minimum 15% (SPEC v2) dan faktor pengali 1,5x untuk skor kepercayaan < 40."""
        # 1. User baru / tanpa skor: 15% dari 10.000.000 = 1.500.000
        min_dep_normal = calculate_min_deposit(10000000, self.renter)
        self.assertEqual(min_dep_normal, 1500000)

        # 2. User None: tetap aman menghasilkan 15%
        self.assertEqual(calculate_min_deposit(5000000, None), 750000)

        # 3. User berisiko tinggi (TrustScore < 40 dan bukan user baru): deposit dikalikan 1.5x
        TrustScore.objects.create(
            user=self.renter,
            score=35,
            risk_probability=0.65,
            is_new_user=False
        )
        min_dep_high_risk = calculate_min_deposit(10000000, self.renter)
        # 15% * 1.5 = 22.5% -> 2.250.000
        self.assertEqual(min_dep_high_risk, 2250000)

    @override_settings(DEPOSIT_MODE='legacy')
    def test_rental_price_summary_matches_project_spec_v2(self):
        """
        Uji contoh perhitungan SPEC v2:
        Kamera Rp75.000/hari, 3 hari = Rp225.000, deposit Rp500.000, proteksi 5% (Rp11.250).
        Total bayar harus tepat Rp736.250.
        """
        start = date(2026, 11, 10)
        end = date(2026, 11, 12)  # 3 hari inklusif (10, 11, 12)

        summary = calculate_rental_summary(
            self.item_kamera, start, end, use_protection=True
        )

        self.assertTrue(summary['is_valid'])
        self.assertEqual(summary['days'], 3)
        self.assertEqual(summary['rent_total'], 225000)
        self.assertEqual(summary['deposit_total'], 500000)
        self.assertEqual(summary['protection_fee'], 11250)
        self.assertEqual(summary['grand_total'], 736250)

    def test_date_availability_and_collision_scenarios(self):
        """
        Uji filter anti double-booking:
        - Tabrakan (overlap)
        - Bersebelahan (adjacent)
        - Tepat di batas (exact boundary)
        """
        # Buat rental aktif yang memblokir: 15 Nov 2026 s/d 18 Nov 2026
        r_start = date(2026, 11, 15)
        r_end = date(2026, 11, 18)
        Rental.objects.create(
            item=self.item_kamera,
            renter=self.renter,
            owner=self.owner,
            start_date=r_start,
            end_date=r_end,
            days=4,
            price_per_day_snapshot=75000,
            rent_total=300000,
            deposit_total=500000,
            grand_total=800000,
            status=Rental.Status.DIBAYAR
        )

        # Kasus 1: Tabrakan di tengah (16 Nov - 17 Nov) -> Tidak tersedia
        self.assertFalse(is_item_available(self.item_kamera, date(2026, 11, 16), date(2026, 11, 17)))

        # Kasus 2: Tepat di batas awal (14 Nov - 15 Nov) -> Tumpang tindih di tgl 15 -> Tidak tersedia
        self.assertFalse(is_item_available(self.item_kamera, date(2026, 11, 14), date(2026, 11, 15)))

        # Kasus 3: Tepat di batas akhir (18 Nov - 20 Nov) -> Tumpang tindih di tgl 18 -> Tidak tersedia
        self.assertFalse(is_item_available(self.item_kamera, date(2026, 11, 18), date(2026, 11, 20)))

        # Kasus 4: Bersebelahan sebelum (10 Nov - 14 Nov) -> Selesai sebelum sewa mulai -> TERSEDIA
        self.assertTrue(is_item_available(self.item_kamera, date(2026, 11, 10), date(2026, 11, 14)))

        # Kasus 5: Bersebelahan sesudah (19 Nov - 22 Nov) -> Mulai setelah sewa selesai -> TERSEDIA
        self.assertTrue(is_item_available(self.item_kamera, date(2026, 11, 19), date(2026, 11, 22)))

    def test_image_resizing_on_upload(self):
        """Uji kompresi dan pengecilan foto maks. 1280 px sisi terpanjang kualitas 80."""
        # Buat gambar dummy ukuran besar (2000 x 1500 px)
        large_image = Image.new('RGB', (2000, 1500), color=(100, 150, 200))
        img_io = io.BytesIO()
        large_image.save(img_io, format='JPEG', quality=95)
        img_io.seek(0)

        uploaded = SimpleUploadedFile(
            'camera_large.jpg', img_io.read(), content_type='image/jpeg'
        )

        photo = ItemPhoto.objects.create(item=self.item_kamera, image=uploaded)

        # Buka kembali gambar tersimpan
        with Image.open(photo.image.path) as saved_img:
            w, h = saved_img.size
            self.assertLessEqual(max(w, h), 1280)
            self.assertEqual(w, 1280)
            self.assertEqual(h, 960)


class CatalogViewsAndAccessTest(TestCase):
    def setUp(self):
        self.client = Client()

        self.owner = User.objects.create_user(
            username='owner_user', email='owner@test.id', password='Password123!',
            full_name='Pemilik Sah', is_verified_student=True
        )
        StudentProfile.objects.create(
            user=self.owner, nim='11112222', campus_name='Univ KampusRent', major='Teknik'
        )

        self.other_user = User.objects.create_user(
            username='other_user', email='other@test.id', password='Password123!',
            full_name='Orang Lain', is_verified_student=True
        )
        StudentProfile.objects.create(
            user=self.other_user, nim='33334444', campus_name='Univ KampusRent', major='Manajemen'
        )

        self.unverified_user = User.objects.create_user(
            username='unverified_user', email='unverified@test.id', password='Password123!',
            full_name='Belum Terverifikasi', is_verified_student=False
        )

        self.category = Category.objects.create(name='Kamera', slug='kamera')
        self.item = Item.objects.create(
            owner=self.owner,
            category=self.category,
            title='Sony A6400 Mirrorless',
            description='Sony A6400 4K video autofocus cepat',
            condition=Item.Condition.SANGAT_BAIK,
            estimated_value=12000000,
            price_per_day=90000,
            deposit_amount=600000,
            min_days=1,
            max_days=5,
            pickup_area='Fakultas Teknik',
            is_active=True
        )

    def test_unverified_user_cannot_create_item(self):
        """Akun belum terverifikasi KTM dilarang memasang barang baru dan diarahkan ke verifikasi."""
        self.client.login(username='unverified_user', password='Password123!')
        response = self.client.get('/barang/baru/')
        # Harus di-redirect ke halaman verifikasi KTM
        self.assertEqual(response.status_code, 302)
        self.assertIn('/verifikasi-ktm/', response.url)

    def test_only_owner_can_edit_item_idor_protection(self):
        """Hanya pemilik barang yang berhak mengubah barang (mencegah IDOR, status 403 untuk orang lain)."""
        # User lain mencoba akses halaman edit milik owner
        self.client.login(username='other_user', password='Password123!')
        response = self.client.get(f'/barang/{self.item.slug}/ubah/')
        self.assertEqual(response.status_code, 403)

        # Pemilik sah bisa membuka halaman ubah
        self.client.login(username='owner_user', password='Password123!')
        response_owner = self.client.get(f'/barang/{self.item.slug}/ubah/')
        self.assertEqual(response_owner.status_code, 200)

    def test_only_owner_can_toggle_active_status(self):
        """Hanya pemilik yang dapat mengaktifkan/menonaktifkan (soft delete) barang."""
        self.client.login(username='other_user', password='Password123!')
        response = self.client.post(f'/barang/{self.item.slug}/toggle-status/')
        self.assertEqual(response.status_code, 403)
        self.item.refresh_from_db()
        self.assertTrue(self.item.is_active)

        # Pemilik sah berhasil menonaktifkan
        self.client.login(username='owner_user', password='Password123!')
        response_owner = self.client.post(f'/barang/{self.item.slug}/toggle-status/')
        self.assertEqual(response_owner.status_code, 302)
        self.item.refresh_from_db()
        self.assertFalse(self.item.is_active)

    def test_catalog_search_and_sorting(self):
        """Uji fungsionalitas pencarian kata kunci dan pengurutan di katalog."""
        # Buat item pembanding dengan harga lebih tinggi
        Item.objects.create(
            owner=self.owner,
            category=self.category,
            title='Canon EOS R6 Mark II',
            description='Kamera full-frame profesional',
            condition=Item.Condition.SANGAT_BAIK,
            estimated_value=30000000,
            price_per_day=250000,
            deposit_amount=1500000,
            is_active=True
        )

        # 1. Cari kata kunci 'Sony'
        resp_sony = self.client.get('/barang/?q=Sony')
        self.assertEqual(resp_sony.status_code, 200)
        self.assertContains(resp_sony, 'Sony A6400')
        self.assertNotContains(resp_sony, 'Canon EOS R6')

        # 2. Urut termurah
        resp_termurah = self.client.get('/barang/?urut=termurah')
        items = list(resp_termurah.context['page_obj'].object_list)
        self.assertEqual(items[0].title, 'Sony A6400 Mirrorless')
        self.assertEqual(items[1].title, 'Canon EOS R6 Mark II')

        # 3. Urut termahal
        resp_termahal = self.client.get('/barang/?urut=termahal')
        items_desc = list(resp_termahal.context['page_obj'].object_list)
        self.assertEqual(items_desc[0].title, 'Canon EOS R6 Mark II')
        self.assertEqual(items_desc[1].title, 'Sony A6400 Mirrorless')

    def test_catalog_query_efficiency_assert_num_queries(self):
        """
        Uji optimasi query (anti N+1):
        select_related(owner, category, owner__trust_score) dan prefetch_related(photos)
        harus mempertahankan query count tetap rendah meskipun jumlah barang bertambah.
        """
        # Tambahkan 5 barang ekstra
        for i in range(5):
            Item.objects.create(
                owner=self.owner,
                category=self.category,
                title=f'Barang Ekstra #{i}',
                description='Deskripsi ekstra',
                condition=Item.Condition.BAIK,
                estimated_value=1000000,
                price_per_day=30000,
                deposit_amount=100000,
                is_active=True
            )

        # Query katalog /barang/hasil/ tidak boleh mengalami ledakan query berulang
        # Harusnya hanya sekitar 3-5 query (active campuses, count, items select_related, photos prefetch)
        with self.assertNumQueries(4):
            response = self.client.get('/barang/hasil/')
            self.assertEqual(response.status_code, 200)

    @override_settings(DEPOSIT_MODE='legacy')
    def test_htmx_receipt_summary_endpoint(self):
        """Uji endpoint HTMX ringkasan kuitansi sewa /barang/<slug>/ringkasan/."""
        response = self.client.get(
            f'/barang/{self.item.slug}/ringkasan/',
            {
                'start_date': '2026-11-01',
                'end_date': '2026-11-03',
                'use_protection': 'true'
            }
        )
        self.assertEqual(response.status_code, 200)
        # 3 hari x 90.000 = 270.000 sewa, deposit 600.000, proteksi 5% (13.500) -> 883.500
        self.assertContains(response, 'Rp270.000')
        self.assertContains(response, 'Rp600.000')
        self.assertContains(response, 'Rp13.500')
        self.assertContains(response, 'Rp883.500')

    def test_max_item_value_rejection_in_form(self):
        """Uji penolakan barang jika estimated_value melebihi MAX_ITEM_VALUE (Rp3.000.000)."""
        form_data = {
            'title': 'Kamera Sinema Mahal',
            'category': self.category.id,
            'description': 'Kamera sinema kelas bioskop',
            'condition': Item.Condition.SANGAT_BAIK,
            'estimated_value': 4500000,  # Melebihi batas Rp3.000.000
            'price_per_day': 150000,
            'deposit_amount': 500000,
            'min_days': 1,
            'max_days': 3,
            'pickup_area': 'Gedung A',
            'min_renter_tier': 'baru',
        }
        form = ItemForm(data=form_data, user=self.owner)
        self.assertFalse(form.is_valid())
        self.assertIn('estimated_value', form.errors)
        self.assertIn('Rp3.000.000', form.errors['estimated_value'][0])

    @override_settings(DEPOSIT_MODE='legacy')
    def test_deposit_minimum_validation_in_form(self):
        """Uji validasi deposit minimum pada form pasang barang."""
        # Barang nilai 1.000.000 -> minimum deposit 15% (150.000)
        form_data = {
            'title': 'Tripod Karbon',
            'category': self.category.id,
            'description': 'Tripod kokoh',
            'condition': Item.Condition.SANGAT_BAIK,
            'estimated_value': 1000000,
            'price_per_day': 25000,
            'deposit_amount': 50000,  # Terlalu rendah (di bawah minimum 150.000)
            'min_days': 1,
            'max_days': 5,
            'pickup_area': 'Gedung A',
            'min_renter_tier': 'baru',
        }
        form = ItemForm(data=form_data, user=self.owner)
        self.assertFalse(form.is_valid())
        self.assertIn('deposit_amount', form.errors)

    def test_catalog_date_filter_scenarios(self):
        """
        Uji filter tanggal katalog di endpoint /barang/:
        Sewa aktif: 15 Nov s/d 18 Nov 2026.
        1. Tabrakan (16 Nov - 17 Nov) -> barang disembunyikan.
        2. Tepat di batas awal (14 Nov - 15 Nov) -> barang disembunyikan.
        3. Tepat di batas akhir (18 Nov - 19 Nov) -> barang disembunyikan.
        4. Bersebelahan (10 Nov - 14 Nov atau 19 Nov - 22 Nov) -> barang TAMPIL.
        """
        Rental.objects.create(
            item=self.item, renter=self.other_user, owner=self.owner,
            start_date=date(2026, 11, 15), end_date=date(2026, 11, 18), days=4,
            price_per_day_snapshot=90000, rent_total=360000, deposit_total=600000, grand_total=960000,
            status=Rental.Status.DIBAYAR
        )

        # 1. Tabrakan (overlap)
        resp_tabrakan = self.client.get('/barang/?kampus=semua&start_date=2026-11-16&end_date=2026-11-17')
        self.assertNotContains(resp_tabrakan, self.item.title)

        # 2. Tepat di batas awal (14 Nov - 15 Nov)
        resp_batas_awal = self.client.get('/barang/?kampus=semua&start_date=2026-11-14&end_date=2026-11-15')
        self.assertNotContains(resp_batas_awal, self.item.title)

        # 3. Tepat di batas akhir (18 Nov - 19 Nov)
        resp_batas_akhir = self.client.get('/barang/?kampus=semua&start_date=2026-11-18&end_date=2026-11-19')
        self.assertNotContains(resp_batas_akhir, self.item.title)

        # 4. Bersebelahan sebelum (10 Nov - 14 Nov) -> Tampil
        resp_sebelum = self.client.get('/barang/?kampus=semua&start_date=2026-11-10&end_date=2026-11-14')
        self.assertContains(resp_sebelum, self.item.title)

        # 5. Bersebelahan sesudah (19 Nov - 22 Nov) -> Tampil
        resp_sesudah = self.client.get('/barang/?kampus=semua&start_date=2026-11-19&end_date=2026-11-22')
        self.assertContains(resp_sesudah, self.item.title)

    def test_catalog_price_condition_and_campus_filters(self):
        """Uji filter katalog: rentang harga, kondisi, dan kampus."""
        campus_a = Campus.objects.create(name='Univ A', short_name='UA')
        campus_b = Campus.objects.create(name='Univ B', short_name='UB')

        self.owner.student_profile.campus = campus_a
        self.owner.student_profile.save()

        # Item 2 milik owner di kampus B
        owner_b = User.objects.create_user(
            username='owner_b', email='b@test.id', password='Password123!',
            full_name='Owner B', is_verified_student=True
        )
        StudentProfile.objects.create(user=owner_b, nim='7777', campus=campus_b, major='Hukum')

        item_b = Item.objects.create(
            owner=owner_b, category=self.category, title='Kamera Kampus B',
            condition=Item.Condition.BAIK, estimated_value=1500000,
            price_per_day=45000, deposit_amount=150000, is_active=True
        )

        # Filter kampus A
        resp_kampus_a = self.client.get(f'/barang/?kampus={campus_a.id}')
        self.assertContains(resp_kampus_a, self.item.title)
        self.assertNotContains(resp_kampus_a, item_b.title)

        # Filter rentang harga (40.000 s/d 50.000)
        resp_harga = self.client.get('/barang/?kampus=semua&harga_min=40000&harga_max=50000')
        self.assertContains(resp_harga, item_b.title)
        self.assertNotContains(resp_harga, self.item.title)

        # Filter kondisi (BAIK)
        resp_kondisi = self.client.get('/barang/?kampus=semua&kondisi=baik')
        self.assertContains(resp_kondisi, item_b.title)
        self.assertNotContains(resp_kondisi, self.item.title)

    def test_catalog_sort_by_owner_trust_score(self):
        """Uji urutan skor pemilik tertinggi di katalog."""
        TrustScore.objects.create(user=self.owner, score=92)

        owner_low = User.objects.create_user(
            username='owner_low', email='low@test.id', password='Password123!',
            full_name='Owner Low Score', is_verified_student=True
        )
        StudentProfile.objects.create(user=owner_low, nim='8888', campus_name='Univ C', major='Teknik')
        TrustScore.objects.create(user=owner_low, score=45)

        item_low = Item.objects.create(
            owner=owner_low, category=self.category, title='Item Low Score Owner',
            condition=Item.Condition.BAIK, estimated_value=800000,
            price_per_day=30000, deposit_amount=100000, is_active=True
        )

        resp = self.client.get('/barang/?kampus=semua&urut=skor_pemilik')
        items = list(resp.context['page_obj'].object_list)
        self.assertEqual(items[0].id, self.item.id)
        self.assertEqual(items[1].id, item_low.id)


class ItemPostingTestCase(TestCase):
    def setUp(self):
        self.campus = Campus.objects.create(name="Univ Lampung", short_name="UNILA", city="Bandar Lampung")
        self.user = User.objects.create_user(
            username='mahasiswa_aktif', email='aktif@unila.ac.id', password='Password123!',
            full_name='Mahasiswa Aktif', is_verified_student=True
        )
        StudentProfile.objects.create(user=self.user, nim='1915061001', campus=self.campus, major='Informatika')
        self.category = Category.objects.create(name='Elektronik', slug='elektronik', order=1)

    def test_item_form_valid_without_min_renter_tier_in_post(self):
        """ItemForm harus tetap valid dan menggunakan nilai default saat min_renter_tier tidak dikirim di POST."""
        form_data = {
            'title': 'Kamera Mirrorless Uji',
            'category': self.category.id,
            'description': 'Kamera kondisi sangat bagus',
            'condition': Item.Condition.SANGAT_BAIK,
            'estimated_value': 1000000,
            'price_per_day': 50000,
            'deposit_amount': 200000,
            'min_days': 1,
            'max_days': 7,
            'pickup_area': 'Gedung Perpustakaan',
        }
        form = ItemForm(data=form_data, user=self.user)
        self.assertTrue(form.is_valid(), f"Errors: {form.errors}")
        item = form.save(commit=False)
        self.assertEqual(item.min_renter_tier, Item.RenterTier.BARU)
        self.assertFalse(item.require_ktm_held)

    def test_item_create_view_with_photo(self):
        """Pengguna terverifikasi berhasil memasang barang baru lengkap dengan foto."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        import io
        from PIL import Image as PILImage

        # Buat dummy PNG image
        img_io = io.BytesIO()
        pil_img = PILImage.new('RGB', (100, 100), color=(73, 109, 137))
        pil_img.save(img_io, format='PNG')
        img_file = SimpleUploadedFile("kamera.png", img_io.getvalue(), content_type="image/png")

        self.client.login(username='mahasiswa_aktif', password='Password123!')
        form_data = {
            'title': 'Proyektor Mini Portable',
            'category': self.category.id,
            'description': 'Proyektor HD jernih',
            'condition': Item.Condition.BAIK,
            'estimated_value': 800000,
            'price_per_day': 40000,
            'deposit_amount': 150000,
            'min_days': 1,
            'max_days': 5,
            'pickup_area': 'Gedung A',
            'photos': [img_file],
        }
        resp = self.client.post('/barang/baru/', form_data, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(Item.objects.filter(title='Proyektor Mini Portable').exists())
        created_item = Item.objects.get(title='Proyektor Mini Portable')
        self.assertEqual(created_item.photos.count(), 1)
        self.assertEqual(created_item.owner, self.user)

    def test_item_create_view_error_feedback_displayed(self):
        """Saat form salah, pesan kesalahan dan alert harus muncul di halaman."""
        self.client.login(username='mahasiswa_aktif', password='Password123!')
        # Nilai estimasi melebihi batas 3.000.000 dan tanpa foto
        form_data = {
            'title': 'Barang Terlalu Mahal',
            'category': self.category.id,
            'description': 'Deskripsi',
            'condition': Item.Condition.BAIK,
            'estimated_value': 5000000,
            'price_per_day': 100000,
            'deposit_amount': 200000,
            'min_days': 1,
            'max_days': 5,
            'pickup_area': 'Gedung A',
        }
        resp = self.client.post('/barang/baru/', form_data)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Terdapat kendala pada isian formulir")
        self.assertContains(resp, "Estimasi nilai barang tidak boleh melebihi")


