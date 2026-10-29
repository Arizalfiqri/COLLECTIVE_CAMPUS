from io import StringIO
from django.test import TestCase, Client, override_settings
from django.core.management import call_command
from django.template.loader import render_to_string
from apps.accounts.services import generate_campus_short_name
from apps.accounts.models import Campus, User, StudentProfile
from apps.catalog.models import Category, Item, ItemPhoto


class Phase7BVisualAndBugFixTest(TestCase):
    def setUp(self):
        self.client = Client(HTTP_HOST='127.0.0.1')

    def test_campus_short_name_never_slices_words(self):
        """generate_campus_short_name tidak memotong kata di tengah dan menghasilkan singkatan bermakna."""
        cases = [
            ("Universitas Sinsar", "US"),
            ("Kampus Seni & Desain", "KSD"),
            ("Institut Teknologi Kampus", "ITK"),
            ("Politeknik Kampus", "PK"),
            ("Institut Teknologi Bandung", "ITB"),
            ("UGM", "UGM"),
            ("UI", "UI"),
        ]
        for name, expected in cases:
            short = generate_campus_short_name(name)
            self.assertEqual(short, expected, f"Short name for '{name}' was '{short}', expected '{expected}'")
            # Pastikan tidak ada kata yang terpotong acak (misal 'Universita' atau 'Kampus Sen')
            self.assertFalse(short.endswith("Universita"))
            self.assertFalse(short.endswith("Kampus Sen"))
            self.assertFalse(short.endswith("Institut T"))

    def test_replace_demo_photos_dry_run_immutability(self):
        """Command replace_demo_photos dalam mode dry-run tidak mengubah atau menghapus data database."""
        campus = Campus.objects.create(name="Universitas Test", short_name="UT", city="Bandung")
        cat = Category.objects.create(name="Elektronik", slug="elektronik")
        user = User.objects.create_user(
            username="demo_tester",
            email="tester@kampus.id",
            password="Password123!"
        )
        StudentProfile.objects.create(user=user, campus=campus, nim="12345001")
        item = Item.objects.create(
            owner=user,
            title="Barang Uji Coba",
            category=cat,
            price_per_day=50000,
            estimated_value=1000000,
            deposit_amount=200000,
            pickup_area="Gedung Rektorat",
            description="Deskripsi uji coba",
            is_active=True
        )
        # Buat foto demo bertanda flat_
        photo = ItemPhoto.objects.create(
            item=item,
            image="items/flat_test.jpg",
            order=0
        )

        initial_count = ItemPhoto.objects.count()
        out = StringIO()
        call_command('replace_demo_photos', stdout=out)
        output_str = out.getvalue()

        self.assertIn("DRY-RUN", output_str)
        self.assertEqual(ItemPhoto.objects.count(), initial_count)
        self.assertTrue(ItemPhoto.objects.filter(pk=photo.pk).exists())

    def test_item_card_fallback_no_text_no_uppercase_labels(self):
        """Kartu barang tanpa foto hanya menampilkan kotak abu solid #E6ECFB dan ikon kamera, tanpa teks."""
        campus = Campus.objects.create(name="Kampus Uji", short_name="KU", city="Jakarta")
        cat = Category.objects.create(name="Kamera", slug="kamera")
        user = User.objects.create_user(
            username="seller_clean",
            email="clean@kampus.id",
            password="Password123!",
            full_name="Budi Santoso"
        )
        StudentProfile.objects.create(user=user, campus=campus, nim="12345002")
        item = Item.objects.create(
            owner=user,
            title="Kamera DSLR Uji",
            category=cat,
            price_per_day=75000,
            estimated_value=4000000,
            deposit_amount=500000,
            pickup_area="Perpustakaan Pusat",
            description="Deskripsi kamera uji",
            is_active=True
        )
        # Item tidak memiliki ItemPhoto
        html = render_to_string("partials/item_card.html", {"item": item})

        # Memiliki background tint #E6ECFB (bg-brand-tint)
        self.assertIn("bg-brand-tint", html)
        # Memiliki ikon kamera
        self.assertIn("<svg", html)
        # Tidak memiliki teks judul barang di dalam fallback thumbnail
        self.assertNotIn("KAMERA DSLR UJI", html)
        self.assertNotIn("Kategori: KAMERA", html)
        self.assertNotIn("BELUM ADA FOTO", html)

    @override_settings(DEBUG=False)
    def test_404_page_contains_tapis_panel_ornament(self):
        """Halaman 404 menyertakan ornamen Tapis Lampung."""
        response = self.client.get('/halaman-pasti-tidak-ada-404-check/')
        self.assertEqual(response.status_code, 404)
        # Ornamen tapis_panel memiliki ciri SVG path diamond / saffron dot
        content = response.content.decode('utf-8')
        self.assertTrue(
            "#EAA225" in content or "tapis" in content.lower() or "d=\"M 0 10 L 10 0 L 20 10" in content,
            "Tapis panel ornament not found in 404 page content."
        )

    def test_step_linear_flow_component_renders(self):
        """Komponen cara kerja steps.html merender alur 5 langkah dengan garis alur horizontal desktop."""
        html = render_to_string("partials/steps.html")
        # Memiliki 5 langkah
        self.assertIn("Verifikasi KTM", html)
        self.assertIn("Ajukan sewa", html)
        self.assertIn("Bayar ke escrow", html)
        self.assertIn("Temu &amp; foto kondisi", html)
        self.assertTrue("Kembali &amp; jaminan cair" in html or "Kembali, pembayaran diteruskan ke pemilik" in html)
        # Memiliki garis desktop dan kelas spesifik
        self.assertIn("h-[2px]", html)
        self.assertIn("bg-line", html)


class Phase7BNusantaraTest(TestCase):
    """
    Pengujian FASE 7B-NUSANTARA:
    1. Chip kategori beranda hanya menampilkan kategori yang punya barang aktif dan 'Lainnya' terakhir.
    2. 'Pencarian populer' disembunyikan bila kurang dari 2 kategori dan dibentuk dinamis dari data.
    3. Halaman 404 dan base template memuat komponen kain_border.
    """
    def setUp(self):
        self.client = Client(HTTP_HOST='127.0.0.1')
        self.campus = Campus.objects.create(name="Universitas Lampung", short_name="UNILA", city="Bandar Lampung")
        self.user = User.objects.create_user(
            username="mahasiswa_uji",
            email="uji@kampus.id",
            password="Password123!",
            full_name="Mahasiswa Uji"
        )
        StudentProfile.objects.create(user=self.user, campus=self.campus, nim="2015061001")

    def _create_item(self, title, category, is_active=True):
        return Item.objects.create(
            owner=self.user,
            title=title,
            category=category,
            price_per_day=50000,
            estimated_value=1000000,
            deposit_amount=200000,
            pickup_area="Gedung GSG",
            description=f"Deskripsi {title}",
            is_active=is_active
        )

    def test_category_chips_only_active_items_and_lainnya_last(self):
        """Chip kategori beranda: hanya kategori dengan min 1 barang aktif, urut terbanyak, 'Lainnya' selalu terakhir."""
        cat_kamera = Category.objects.create(name="Kamera", slug="kamera", order=1)
        cat_audio = Category.objects.create(name="Audio", slug="audio", order=2)
        cat_toga = Category.objects.create(name="Toga", slug="toga", order=3)
        cat_lainnya = Category.objects.create(name="Lainnya", slug="lainnya", order=4)
        cat_buku = Category.objects.create(name="Buku", slug="buku", order=5)

        # Kamera: 3 barang aktif
        for i in range(3):
            self._create_item(f"Kamera {i}", cat_kamera, is_active=True)

        # Audio: 1 barang aktif
        self._create_item("Mic Audio", cat_audio, is_active=True)

        # Lainnya: 2 barang aktif
        for i in range(2):
            self._create_item(f"Barang Unik {i}", cat_lainnya, is_active=True)

        # Toga: hanya barang NON-AKTIF (is_active=False)
        self._create_item("Toga Wisuda Rusak", cat_toga, is_active=False)

        # Buku: 0 barang sama sekali

        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

        categories = response.context['categories']
        slugs = [c.slug for c in categories]

        # Hanya kategori yang punya barang aktif
        self.assertIn("kamera", slugs)
        self.assertIn("audio", slugs)
        self.assertIn("lainnya", slugs)
        self.assertNotIn("toga", slugs, "Kategori dengan hanya barang non-aktif tidak boleh muncul di chip.")
        self.assertNotIn("buku", slugs, "Kategori tanpa barang tidak boleh muncul di chip.")

        # Urutan: Kamera (3) > Audio (1), dan 'Lainnya' (2) selalu terakhir
        self.assertEqual(slugs, ["kamera", "audio", "lainnya"],
                         "Kategori harus diurutkan barang terbanyak dan 'Lainnya' harus selalu berada di urutan paling akhir.")

        # Uji saat 'Lainnya' tidak punya barang aktif: tidak boleh muncul sama sekali
        Item.objects.filter(category=cat_lainnya).delete()
        response2 = self.client.get('/')
        slugs2 = [c.slug for c in response2.context['categories']]
        self.assertNotIn("lainnya", slugs2, "'Lainnya' tidak boleh muncul bila tidak memiliki barang aktif.")

    def test_popular_search_hidden_when_under_two_categories(self):
        """Pencarian populer disembunyikan bila kurang dari 2 kategori yang memiliki barang aktif."""
        cat_kamera = Category.objects.create(name="Kamera", slug="kamera")
        cat_toga = Category.objects.create(name="Toga", slug="toga")

        # Kasus 0: Belum ada barang aktif sama sekali
        res0 = self.client.get('/')
        self.assertNotIn("Pencarian populer:", res0.content.decode('utf-8'))

        # Kasus 1: Hanya 1 kategori yang memiliki barang aktif
        self._create_item("Kamera Mirrorless", cat_kamera, is_active=True)
        res1 = self.client.get('/')
        content1 = res1.content.decode('utf-8')
        self.assertNotIn("Pencarian populer:", content1,
                         "Pencarian populer harus disembunyikan jika kurang dari 2 kategori.")

        # Kasus 2: 2 kategori memiliki barang aktif -> tampil dinamis
        self._create_item("Toga Wisuda Sarjana", cat_toga, is_active=True)
        res2 = self.client.get('/')
        content2 = res2.content.decode('utf-8')
        self.assertIn("Pencarian populer:", content2,
                      "Pencarian populer harus tampil ketika terdapat minimal 2 kategori berbarang aktif.")
        self.assertIn("/barang/?kategori=kamera", content2)
        self.assertIn("/barang/?kategori=toga", content2)

    @override_settings(DEBUG=False)
    def test_footer_contains_kain_border_and_no_navbar_ribbon(self):
        """FASE 7B-NUSANTARA 2: pita bawah navbar dihapus, hanya pita di atas footer dan blok Bukti."""
        res_home = self.client.get('/')
        content_home = res_home.content.decode('utf-8')
        # Navbar bersih: tidak memuat kain_border
        header_part = content_home.split('</header>')[0]
        self.assertNotIn("kain_border", header_part)
        self.assertNotIn("tumpal_hollow", header_part)

        # Pita atas footer tetap ada (ink responsive dengan tumpal saffron)
        self.assertIn("tumpal_hollow_saffron", content_home)


class Phase7BNusantara2Test(TestCase):
    """
    Pengujian FASE 7B-NUSANTARA 2:
    1. Navbar bersih tanpa pita ornamen di bawahnya di semua halaman.
    2. Halaman 404 memuat aset kapal.svg dan tapis-tile.svg.
    3. Halaman Tentang memuat siger.svg pada header dan seksi gotong royong.
    4. Validasi kalkulator terhadap batas tingkat penyewa (menampilkan pesan jelas dan mengosongkan hasil bila melebihi).
    5. Kartu barang demo menggunakan ilustrasi datar tanpa teks di dalam gambar.
    6. Slogan 'Saling sewa, saling bantu.' hadir di footer dan meta description.
    """
    def setUp(self):
        self.client = Client(HTTP_HOST='127.0.0.1')
        self.campus = Campus.objects.create(name="Universitas Lampung", short_name="UNILA", city="Bandar Lampung")
        self.user = User.objects.create_user(
            username="penyewa_baru",
            email="baru@kampus.id",
            password="Password123!",
            full_name="Penyewa Baru"
        )
        StudentProfile.objects.create(user=self.user, campus=self.campus, nim="2015061099")

    def test_navbar_clean_without_ribbon_on_all_pages(self):
        """Navbar di semua halaman harus bersih tanpa pita ornamen di bawahnya."""
        pages = ['/', '/barang/', '/tentang/', '/bantuan/']
        for url in pages:
            res = self.client.get(url)
            self.assertEqual(res.status_code, 200, f"Gagal memuat {url}")
            content = res.content.decode('utf-8')
            header_html = content.split('</header>')[0]
            self.assertNotIn("tumpal_hollow", header_html, f"Pita tumpal tidak boleh ada di header {url}")
            self.assertIn("logo-mark.svg", header_html, f"Logo mark siger harus tampil di header {url}")

    @override_settings(DEBUG=False)
    def test_404_page_loads_kapal_and_tapis_tile(self):
        """Halaman 404 galat harus memuat aset kapal.svg dan latar tapis-tile.svg."""
        res = self.client.get('/halaman-ini-tidak-mungkin-ada-404/')
        self.assertEqual(res.status_code, 404)
        content = res.content.decode('utf-8')
        self.assertIn("kapal.svg", content, "Halaman 404 harus memuat ilustrasi kapal.svg")
        self.assertIn("tapis-tile.svg", content, "Halaman 404 harus menggunakan latar pola tapis-tile.svg")

    def test_tentang_page_loads_siger_and_disclaimer(self):
        """Halaman Tentang memuat siger.svg pada header panel dan keterangan inspirasi geometris."""
        res = self.client.get('/tentang/')
        self.assertEqual(res.status_code, 200)
        content = res.content.decode('utf-8')
        self.assertIn("siger.svg", content, "Halaman Tentang harus memuat siger.svg")
        self.assertIn("tapis-tile.svg", content, "Halaman Tentang harus menggunakan latar tapis-tile.svg")
        self.assertIn("terinspirasi kain tapis dan siger Lampung, digambar ulang secara geometris", content)

    def test_calculator_validation_exceeding_tier_limits(self):
        """Validasi nilai barang terhadap batas tingkat penyewa: menampilkan pesan jelas & kosongkan hasil."""
        # 1. Penyewa baru: batas Rp750.000 -> coba Rp1.000.000 (melebihi)
        res_exceeded = self.client.get('/kalkulator-sewa/?price_per_day=40000&days=3&tier=baru&estimated_value=1000000')
        self.assertEqual(res_exceeded.status_code, 200)
        content_exceeded = res_exceeded.content.decode('utf-8')
        self.assertIn("Batas nilai sewa terlampaui", content_exceeded)
        self.assertIn("Penyewa baru dapat menyewa barang hingga Rp750.000", content_exceeded)
        self.assertNotIn("Total dibayar penyewa di awal", content_exceeded, "Hasil kalkulasi harus dikosongkan.")

        # 2. Penyewa baru: nilai Rp500.000 (tidak melebihi) -> hasil kalkulasi tampil
        res_ok = self.client.get('/kalkulator-sewa/?price_per_day=40000&days=3&tier=baru&estimated_value=500000')
        self.assertEqual(res_ok.status_code, 200)
        content_ok = res_ok.content.decode('utf-8')
        self.assertNotIn("Batas nilai sewa terlampaui", content_ok)
        self.assertIn("Total dibayar penyewa di awal", content_ok)

    def test_slogan_in_footer_and_meta(self):
        """Slogan merek bawaan 'Saling sewa, saling bantu.' ada di footer dan meta description."""
        res = self.client.get('/')
        content = res.content.decode('utf-8')
        self.assertIn('content="Saling sewa, saling bantu.', content)
        self.assertIn('Saling sewa, saling bantu.', content.split('<footer')[1])

    def test_demo_photos_are_flat_illustrations_without_text(self):
        """Memastikan generator replace_demo_photos menghasilkan berkas flat_* tanpa teks."""
        from apps.catalog.management.commands.replace_demo_photos import determine_icon_type
        # Uji mapping kata kunci
        self.assertEqual(determine_icon_type("Canon EOS M50 Mark II", "Kamera"), "kamera")
        self.assertEqual(determine_icon_type("Tripod Takara ECO-196A", "Kamera"), "tripod")
        self.assertEqual(determine_icon_type("Speaker Portable JBL Flip 6", "Audio"), "speaker")
        self.assertEqual(determine_icon_type("Set Toga Wisuda S1", "Wisuda"), "topi_toga")
        self.assertEqual(determine_icon_type("Tenda Camping 4 Orang", "Camping"), "tenda")
        self.assertEqual(determine_icon_type("Kompor Portable", "Camping"), "api")

    def test_new_icon_types_and_category_tile_colors(self):
        """Memverifikasi pemetaan warna ubin per kategori dan ikon khusus: gaun, jas, tas_tidur, speaker."""
        from apps.catalog.management.commands.replace_demo_photos import determine_icon_type, get_category_tile_color

        # 1. Warna ubin tetap per kategori (Fase 7F nada lembut)
        self.assertEqual(get_category_tile_color("kamera", "Kamera & Lensa"), '#8EA8F7')
        self.assertEqual(get_category_tile_color("laptop", "Laptop & Aksesori"), '#8EA8F7')
        self.assertEqual(get_category_tile_color("praktikum", "Alat Praktikum"), '#7ACFAC')
        self.assertEqual(get_category_tile_color("proyektor", "Proyektor & Audio"), '#7ACFAC')
        self.assertEqual(get_category_tile_color("camping", "Camping & Outdoor"), '#FFA68C')
        self.assertEqual(get_category_tile_color("lain-lain", "Lain-lain"), '#FFA68C')
        self.assertEqual(get_category_tile_color("wisuda", "Perlengkapan Wisuda"), '#FFD66B')
        self.assertEqual(get_category_tile_color("kostum", "Kostum & Busana Acara"), '#FFD66B')

        # 2. Ikon baru khusus
        self.assertEqual(determine_icon_type("Jas Formal Pria Hitam", "Kostum"), 'jas')
        self.assertEqual(determine_icon_type("Kebaya Modern Wanita", "Kostum"), 'gaun')
        self.assertEqual(determine_icon_type("Gaun Pesta Merah", "Kostum"), 'gaun')
        self.assertEqual(determine_icon_type("Sleeping Bag Consina", "Camping"), 'tas_tidur')
        self.assertEqual(determine_icon_type("Speaker Portable JBL", "Audio"), 'speaker')

    def test_dashboard_identity_mask_nim_and_sentence_case(self):
        """Dashboard memuat kartu header berpita kain, sapaan nama depan, NIM tersamarkan, dan sentence case."""
        campus = Campus.objects.create(name="Universitas Test", short_name="UT", city="Bandung")
        user = User.objects.create_user(
            username="budi_test",
            first_name="Budi",
            last_name="Santoso",
            email="budi@kampus.id",
            password="Password123!"
        )
        user.is_verified_student = True
        user.save()
        StudentProfile.objects.create(user=user, campus=campus, nim="2359201022", major="Informatika")

        self.client.force_login(user)
        res = self.client.get('/dashboard/')
        self.assertEqual(res.status_code, 200)
        content = res.content.decode('utf-8')

        # Sapaan nama depan dan pita kain
        self.assertIn("Halo, Budi", content)
        self.assertIn("tumpal_hollow_saffron_sm.svg", content)
        # NIM disamarkan (hanya 4 digit terakhir)
        self.assertIn("•••• 1022", content)
        self.assertNotIn("2359201022", content, "NIM penuh tidak boleh bocor di kartu status KTM.")
        # Sentence case tabs & buttons
        self.assertIn("Sewa saya", content)
        self.assertIn("Permintaan masuk", content)
        self.assertIn("Barang saya", content)
        self.assertIn("Ulasan", content)
        self.assertIn("Pasang barang", content)
        # Empty state menggunakan kapal.svg
        self.assertIn("kapal.svg", content)

    def test_ktm_stepper_illustrative_card_and_sentence_case(self):
        """Halaman verifikasi KTM memuat kartu KTM ilustratif berbingkai kain tapis 8px tanpa teks di atas pola."""
        campus = Campus.objects.create(name="Universitas Test 2", short_name="UT2", city="Bandung")
        user = User.objects.create_user(
            username="rina_test",
            first_name="Rina",
            last_name="Pratiwi",
            email="rina@kampus.id",
            password="Password123!"
        )
        StudentProfile.objects.create(user=user, campus=campus, nim="2359201033", major="Sistem Informasi")

        self.client.force_login(user)
        res = self.client.get('/verifikasi-ktm/?step=1')
        self.assertEqual(res.status_code, 200)
        content = res.content.decode('utf-8')

        self.assertIn("tapis-tile.svg", content, "Kartu KTM ilustratif harus menggunakan bingkai tapis-tile.svg")
        self.assertIn("Kartu Tanda Mahasiswa", content)
        self.assertIn("•••• 1033", content)
        self.assertIn("1. Data diri", content)
        self.assertIn("2. Unggah KTM", content)
        self.assertIn("3. Status &amp; tinjauan", content)

    def test_rename_demo_codes_dry_run_and_apply(self):
        """Perintah rename_demo_codes: dry-run tidak mengubah data, apply mengubah kode ke KR-XXXXXX aman dan konsisten."""
        from datetime import date
        from apps.rentals.models import Rental
        from apps.payments.models import Payment, LedgerEntry

        campus = Campus.objects.create(name="Universitas Test 3", short_name="UT3", city="Bandung")
        cat = Category.objects.create(name="Kamera", slug="kamera-test")
        owner = User.objects.create_user(username="owner_demo", email="owner@test.id", password="password")
        renter = User.objects.create_user(username="renter_demo", email="renter@test.id", password="password")
        item = Item.objects.create(
            owner=owner, title="Kamera Uji", category=cat,
            price_per_day=50000, estimated_value=1000000, deposit_amount=200000,
            pickup_area="Kampus"
        )

        test_code = "KR-DEMO99"
        rental = Rental.objects.create(
            code=test_code,
            item=item,
            owner=owner,
            renter=renter,
            start_date=date(2026, 10, 20),
            end_date=date(2026, 10, 22),
            days=2,
            rent_total=100000,
            deposit_total=200000,
            grand_total=300000,
            status=Rental.Status.SELESAI
        )
        payment = Payment.objects.create(
            rental=rental,
            order_id=f"KR-{test_code}-01",
            gross_amount=300000,
            status='settlement'
        )
        ledger = LedgerEntry.objects.create(
            rental=rental,
            kind='masuk_sewa',
            amount=100000,
            note=f"Penerimaan sewa ({test_code})"
        )

        # 1. Dry run tidak mengubah apapun
        out = StringIO()
        call_command('rename_demo_codes', stdout=out)
        rental.refresh_from_db()
        self.assertEqual(rental.code, test_code, "Dry-run tidak boleh mengubah kode di database.")

        # 2. Apply mengubah kode sewa dan menjaga konsistensi relasi
        out_apply = StringIO()
        call_command('rename_demo_codes', '--apply', stdout=out_apply)
        rental.refresh_from_db()
        payment.refresh_from_db()
        ledger.refresh_from_db()

        self.assertNotEqual(rental.code, test_code)
        self.assertTrue(rental.code.startswith("KR-"))
        self.assertEqual(len(rental.code), 9)  # 'KR-' (3) + 6 chars = 9
        self.assertNotIn("DEMO", rental.code)
        # Order ID dan Ledger Entry ikut tersinkronkan
        self.assertIn(rental.code, payment.order_id)
        self.assertIn(rental.code, ledger.note)



