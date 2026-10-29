from django.test import TestCase, Client
from django.urls import reverse
from apps.accounts.models import User
from apps.core.models import Notification


class NotificationViewsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='user_notif',
            email='notif@kampus.id',
            password='Password123!',
            full_name='User Notif'
        )
        self.other_user = User.objects.create_user(
            username='user_other',
            email='other@kampus.id',
            password='Password123!',
            full_name='User Other'
        )
        self.client = Client(HTTP_HOST='127.0.0.1')

    def test_anonymous_redirected_to_login(self):
        """Pengguna anonim yang membuka /notifikasi/ dialihkan ke dashboard lalu login."""
        response = self.client.get(reverse('core:notifications'), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(any('/masuk/' in url for url, _ in response.redirect_chain))

    def test_authenticated_user_notifications_redirects_to_dashboard(self):
        """Halaman lama /notifikasi/ sekarang dialihkan ke /dashboard/ karena notifikasi tampil sebagai modal HTMX."""
        self.client.force_login(self.user)
        response = self.client.get(reverse('core:notifications'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/dashboard/')

    def test_mark_all_notifications_read(self):
        """Aksi tandai semua dibaca mengubah status is_read menjadi True."""
        Notification.notify(user=self.user, title='Notif 1', message='Pesan 1')
        Notification.notify(user=self.user, title='Notif 2', message='Pesan 2')

        self.client.force_login(self.user)
        response = self.client.post(reverse('core:mark_all_read'))
        self.assertEqual(response.status_code, 200)

        unread_count = Notification.objects.filter(user=self.user, is_read=False).count()
        self.assertEqual(unread_count, 0)

    def test_click_notification_marks_read_and_redirects(self):
        """Mengklik notifikasi menandai is_read=True, mengurangi counter belum dibaca, dan redirect ke URL tujuan."""
        notif = Notification.notify(
            user=self.user,
            title='Jadwal Temu',
            message='Pemilik telah mengusulkan jadwal temu.',
            url='/sewa/KR-TEST01/'
        )
        self.assertFalse(notif.is_read)

        self.client.force_login(self.user)
        # Sebelum klik: unread count = 1
        self.assertEqual(Notification.objects.filter(user=self.user, is_read=False).count(), 1)

        # Klik notifikasi
        response = self.client.get(reverse('core:notification_click', kwargs={'pk': notif.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/sewa/KR-TEST01/')

        # Sesudah klik: is_read menjadi True dan counter belum dibaca berkurang otomatis ke 0
        notif.refresh_from_db()
        self.assertTrue(notif.is_read)
        self.assertEqual(Notification.objects.filter(user=self.user, is_read=False).count(), 0)

    def test_cannot_click_other_user_notification(self):
        """User lain tidak dapat membuka atau membaca notifikasi milik user lain (404)."""
        notif_other = Notification.notify(
            user=self.other_user,
            title='Rahasia',
            message='Pesan rahasia',
            url='/sewa/KR-OTHER/'
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse('core:notification_click', kwargs={'pk': notif_other.pk}))
        self.assertEqual(response.status_code, 404)
        notif_other.refresh_from_db()
        self.assertFalse(notif_other.is_read)



class StaticPagesTest(TestCase):
    def setUp(self):
        self.client = Client(HTTP_HOST='127.0.0.1')

    def test_tentang_page_loads(self):
        """Halaman /tentang/ dapat diakses publik dengan status 200."""
        response = self.client.get(reverse('core:tentang'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Tentang')
        self.assertContains(response, 'Collective Campus')
        self.assertContains(response, 'Dana Gotong Royong')

    def test_bantuan_page_loads(self):
        """Halaman /bantuan/ dapat diakses publik dengan status 200."""
        response = self.client.get(reverse('core:bantuan'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Pusat Bantuan')
        self.assertContains(response, 'Verifikasi dan akun')
        self.assertContains(response, 'Dana Gotong Royong')
        self.assertContains(response, 'Escrow')

