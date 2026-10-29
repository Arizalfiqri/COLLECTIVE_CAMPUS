from django.db import migrations


SALE_CATEGORIES = [
    {
        'name': 'Pakaian dan thrift',
        'slug': 'pakaian-thrift',
        'icon': 'shirt',
        'order': 101,
        'scope': 'jual',
    },
    {
        'name': 'Buku dan alat kuliah',
        'slug': 'buku-alat-kuliah',
        'icon': 'graduation-cap',
        'order': 102,
        'scope': 'jual',
    },
    {
        'name': 'Elektronik',
        'slug': 'elektronik-jual',
        'icon': 'laptop',
        'order': 103,
        'scope': 'jual',
    },
    {
        'name': 'Perabot kos',
        'slug': 'perabot-kos',
        'icon': 'package',
        'order': 104,
        'scope': 'jual',
    },
    {
        'name': 'Hobi dan olahraga',
        'slug': 'hobi-olahraga',
        'icon': 'tent',
        'order': 105,
        'scope': 'jual',
    },
    {
        'name': 'Lainnya',
        'slug': 'lainnya-jual',
        'icon': 'package',
        'order': 106,
        'scope': 'jual',
    },
]


def seed_sale_categories(apps, schema_editor):
    Category = apps.get_model('catalog', 'Category')
    for cat_data in SALE_CATEGORIES:
        Category.objects.update_or_create(
            slug=cat_data['slug'],
            defaults={
                'name': cat_data['name'],
                'icon': cat_data['icon'],
                'order': cat_data['order'],
                'scope': cat_data['scope'],
            }
        )


def unseed_sale_categories(apps, schema_editor):
    Category = apps.get_model('catalog', 'Category')
    slugs = [c['slug'] for c in SALE_CATEGORIES]
    Category.objects.filter(slug__in=slugs).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0005_category_scope_alter_category_name_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_sale_categories, reverse_code=unseed_sale_categories),
    ]
