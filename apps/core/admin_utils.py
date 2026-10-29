import csv
from django.http import HttpResponse


def generate_csv_export_action(description, filename_prefix, columns):
    """
    Generator aksi ekspor CSV serbaguna untuk Django ModelAdmin.
    columns: list of tuples (header_label, accessor_func_or_attr_name)
    """
    def export_as_csv(modeladmin, request, queryset):
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{filename_prefix}.csv"'
        writer = csv.writer(response)

        headers = [col[0] for col in columns]
        writer.writerow(headers)

        for obj in queryset:
            row = []
            for col in columns:
                accessor = col[1]
                if callable(accessor):
                    try:
                        val = accessor(obj)
                    except Exception:
                        val = ""
                else:
                    val = getattr(obj, accessor, "")
                if val is None:
                    val = ""
                row.append(str(val))
            writer.writerow(row)
        return response

    export_as_csv.short_description = description
    return export_as_csv
