from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.accounts.models import Campus, StudentProfile

User = get_user_model()


class Phase9InteriorPagesTests(TestCase):
    def setUp(self):
        self.campus = Campus.objects.create(
            name='Institut Teknologi Metro',
            short_name='ITM',
            city='Metro',
            is_active=True,
        )
        self.user = User.objects.create_user(
            username='mahasiswa_interior',
            email='mhs@itm.ac.id',
            password='Password123!',
            is_verified_student=True,
        )
        self.profile = StudentProfile.objects.create(
            user=self.user,
            campus=self.campus,
            nim='12345678',
            major='Teknik Informatika',
        )

    def test_interior_pages_no_pills_above_h1(self):
        """Halaman interior tidak boleh memiliki pill kecil di atas h1."""
        urls_to_check = [
            reverse('core:kontak'),
            reverse('core:syarat_ketentuan'),
            reverse('core:kebijakan_privasi'),
            reverse('core:panduan_komunitas'),
            reverse('accounts:resend_verification'),
            reverse('accounts:password_reset'),
        ]
        for url in urls_to_check:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, f"Gagal akses {url}")
            content = response.content.decode('utf-8')
            # Tidak boleh ada span pill uppercase di atas h1
            self.assertNotRegex(
                content,
                r'<span class="[^"]*uppercase tracking-wider[^"]*">\s*[^<]+\s*</span>\s*<h1',
                f"Ditemukan pill uppercase di atas h1 pada {url}"
            )

    def test_auth_interior_pages_authenticated(self):
        """Halaman interior yang memerlukan login tidak boleh memiliki pill di atas h1."""
        self.client.force_login(self.user)
        auth_urls = [
            reverse('catalog:item_create'),
            reverse('catalog:my_items'),
            reverse('sales:item_create'),
            reverse('sales:my_items'),
            reverse('verification:ktm_stepper'),
        ]
        for url in auth_urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, f"Gagal akses {url}")
            content = response.content.decode('utf-8')
            self.assertNotRegex(
                content,
                r'<span class="[^"]*uppercase tracking-wider[^"]*">\s*[^<]+\s*</span>\s*<h1',
                f"Ditemukan pill uppercase di atas h1 pada {url}"
            )

    def test_sewa_dan_jual_beli_coverage_in_core_pages(self):
        """Halaman kontak, legal, dan akun harus menyebut sewa dan jual beli secara seimbang."""
        # Kontak
        response = self.client.get(reverse('core:kontak'))
        content = response.content.decode('utf-8').lower()
        self.assertIn('sewa', content)
        self.assertIn('jual beli', content)

        # Syarat & ketentuan
        response = self.client.get(reverse('core:syarat_ketentuan'))
        content = response.content.decode('utf-8').lower()
        self.assertIn('sewa', content)
        self.assertIn('jual beli', content)

        # Kebijakan privasi
        response = self.client.get(reverse('core:kebijakan_privasi'))
        content = response.content.decode('utf-8').lower()
        self.assertIn('sewa', content)
        self.assertIn('jual beli', content)

        # Panduan komunitas
        response = self.client.get(reverse('core:panduan_komunitas'))
        content = response.content.decode('utf-8').lower()
        self.assertIn('sewa', content)
        self.assertIn('jual beli', content)

    def test_dashboard_and_register_coverage(self):
        """Halaman pendaftaran dan dashboard harus mencakup sewa dan jual beli."""
        response = self.client.get(reverse('accounts:register'))
        content = response.content.decode('utf-8').lower()
        self.assertIn('sewa', content)
        self.assertIn('jual beli', content)

        self.client.force_login(self.user)
        response = self.client.get(reverse('accounts:dashboard'))
        content = response.content.decode('utf-8').lower()
        self.assertIn('sewa', content)
        self.assertIn('jual beli', content)
