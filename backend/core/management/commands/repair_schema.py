"""
Add any database columns the models expect but the table doesn't have.

Why this exists: migrations are generated fresh in each copy of the project, so
a database created from an older `0001_initial` already has that name recorded
as applied. A newer `0001_initial` containing extra fields is then skipped —
`migrate` reports "No migrations to apply" and the columns never appear. The
first request that touches one fails with a 500.

This compares every model field against the live table and adds what's missing,
using Django's own schema editor so the column types are exactly what the ORM
expects. Existing data is untouched.

    python manage.py repair_schema --dry-run
    python manage.py repair_schema
"""
from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Add missing columns so the database matches the models."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="Report what's missing without changing anything")

    def handle(self, *args, **opts):
        dry = opts["dry_run"]
        tables = set(connection.introspection.table_names())
        missing_total = 0

        for model in apps.get_app_config("core").get_models():
            table = model._meta.db_table
            if table not in tables:
                self.stdout.write(self.style.ERROR(
                    f"  table {table} doesn't exist at all — run migrate first"
                ))
                continue

            with connection.cursor() as cursor:
                have = {c.name for c in connection.introspection.get_table_description(cursor, table)}

            for field in model._meta.local_fields:
                if not field.column or field.column in have:
                    continue

                missing_total += 1
                self.stdout.write(
                    f"  {table}.{field.column}  ({field.get_internal_type()})"
                )
                if dry:
                    continue

                # A NOT NULL column can't be added to a table with rows unless
                # it has a default, so say so plainly rather than crashing.
                if not field.null and not field.has_default():
                    self.stdout.write(self.style.ERROR(
                        f"    can't add: it's NOT NULL with no default. "
                        f"Give it null=True or a default, then re-run."
                    ))
                    continue

                with connection.schema_editor() as editor:
                    editor.add_field(model, field)
                self.stdout.write(self.style.SUCCESS("    added"))

        if missing_total == 0:
            self.stdout.write(self.style.SUCCESS(
                "\n  Database matches the models. Nothing to repair.\n"
            ))
        elif dry:
            self.stdout.write(self.style.WARNING(
                f"\n  {missing_total} column(s) missing. Re-run without --dry-run to add them.\n"
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"\n  Repaired {missing_total} column(s). Restart the server.\n"
            ))
