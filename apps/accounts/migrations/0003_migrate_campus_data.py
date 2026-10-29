from django.db import migrations


def migrate_campus_data(apps, schema_editor):
    Campus = apps.get_model('accounts', 'Campus')
    MeetingPoint = apps.get_model('accounts', 'MeetingPoint')
    StudentProfile = apps.get_model('accounts', 'StudentProfile')

    # 1. Pastikan 3 Kampus Fiktif Utama terbuat (SPEC v2 Bagian F)
    ukr, _ = Campus.objects.get_or_create(
        name='Universitas KampusRent',
        defaults={
            'short_name': 'UKR',
            'city': 'Bandung',
            'ktm_keywords': ['universitas kampusrent', 'kampusrent', 'ukr'],
            'nim_pattern': r'^\d{10}$',
            'is_active': True,
        }
    )
    itm, _ = Campus.objects.get_or_create(
        name='Institut Teknologi Mahasiswa',
        defaults={
            'short_name': 'ITM',
            'city': 'Jakarta',
            'ktm_keywords': ['institut teknologi mahasiswa', 'itm'],
            'nim_pattern': r'^\d{8}$',
            'is_active': True,
        }
    )
    pnp, _ = Campus.objects.get_or_create(
        name='Politeknik Negeri Pelajar',
        defaults={
            'short_name': 'PNP',
            'city': 'Surabaya',
            'ktm_keywords': ['politeknik negeri pelajar', 'pnp'],
            'nim_pattern': r'^\d{9}$',
            'is_active': True,
        }
    )

    # 2. Titik temu untuk masing-masing kampus (SPEC v2 Bagian D & F)
    # Titik temu UKR
    MeetingPoint.objects.get_or_create(campus=ukr, name='Perpustakaan Pusat', defaults={'is_public': True})
    MeetingPoint.objects.get_or_create(campus=ukr, name='Kantin Barat', defaults={'is_public': True})
    MeetingPoint.objects.get_or_create(campus=ukr, name='Gedung Rektorat Lt. 1', defaults={'is_public': True})
    MeetingPoint.objects.get_or_create(campus=ukr, name='Lobi Gedung Kuliah Bersama', defaults={'is_public': False})

    # Titik temu ITM
    MeetingPoint.objects.get_or_create(campus=itm, name='Plaza Utama', defaults={'is_public': True})
    MeetingPoint.objects.get_or_create(campus=itm, name='Gedung Labtek V', defaults={'is_public': True})
    MeetingPoint.objects.get_or_create(campus=itm, name='Kantin Borju', defaults={'is_public': True})

    # Titik temu PNP
    MeetingPoint.objects.get_or_create(campus=pnp, name='Gerbang Utama', defaults={'is_public': True})
    MeetingPoint.objects.get_or_create(campus=pnp, name='Student Center', defaults={'is_public': True})
    MeetingPoint.objects.get_or_create(campus=pnp, name='Bengkel Mesin Terpadu', defaults={'is_public': False})

    # 3. Pindahkan data lama StudentProfile.campus_name ke ForeignKey campus
    for profile in StudentProfile.objects.all():
        if profile.campus_id is None:
            c_name = getattr(profile, 'campus_name', '').strip()
            if c_name:
                matched_campus = Campus.objects.filter(name__iexact=c_name).first()
                if not matched_campus:
                    matched_campus, _ = Campus.objects.get_or_create(
                        name=c_name,
                        defaults={
                            'short_name': c_name[:10].strip(),
                            'city': 'Bandung',
                            'ktm_keywords': [c_name.lower()],
                            'is_active': True,
                        }
                    )
                profile.campus = matched_campus
            else:
                profile.campus = ukr
            profile.save(update_fields=['campus'])


def reverse_migrate_campus_data(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_blacklistednim_campus_user_is_suspended_and_more'),
    ]

    operations = [
        migrations.RunPython(migrate_campus_data, reverse_migrate_campus_data),
    ]
