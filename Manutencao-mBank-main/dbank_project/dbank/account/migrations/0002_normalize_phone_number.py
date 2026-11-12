from django.db import migrations, models


def normalize_phone_numbers(apps, schema_editor):
    client_model = apps.get_model('account', 'Client')
    client_model.objects.using(schema_editor.connection.alias).filter(
        phone_number__isnull=True
    ).update(phone_number='')


class Migration(migrations.Migration):
    dependencies = [('account', '0001_initial')]

    operations = [
        migrations.RunPython(normalize_phone_numbers, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='client',
            name='phone_number',
            field=models.CharField('phone number', max_length=64, blank=True),
        ),
    ]
