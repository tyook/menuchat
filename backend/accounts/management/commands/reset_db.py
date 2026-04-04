import sys

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Reset the database by dropping all tables and re-running migrations."

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-input",
            action="store_true",
            dest="no_input",
            help="Skip the confirmation prompt.",
        )
        parser.add_argument(
            "--flush-only",
            action="store_true",
            help="Delete all data but keep the schema (faster, no migration re-run).",
        )

    def handle(self, *args, **options):
        db_name = settings.DATABASES["default"]["NAME"]

        if not options["no_input"]:
            self.stderr.write(
                self.style.WARNING(
                    f'This will destroy ALL data in database "{db_name}". '
                    "This action cannot be undone."
                )
            )
            confirm = input("Type 'yes' to continue: ")
            if confirm != "yes":
                self.stderr.write(self.style.NOTICE("Aborted."))
                sys.exit(1)

        if options["flush_only"]:
            self._flush()
        else:
            self._full_reset()

        self.stdout.write(self.style.SUCCESS("Database reset complete."))

    def _flush(self):
        self.stdout.write("Flushing all data (keeping schema)...")
        call_command("flush", "--no-input", verbosity=0)

    def _full_reset(self):
        self.stdout.write("Dropping all tables...")
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public';"
            )
            tables = [row[0] for row in cursor.fetchall()]
            if tables:
                cursor.execute(
                    "DROP TABLE IF EXISTS {} CASCADE;".format(
                        ", ".join(f'"{t}"' for t in tables)
                    )
                )
            # Drop custom enum types that Django migrations create
            cursor.execute(
                "SELECT typname FROM pg_type "
                "WHERE typnamespace = 'public'::regnamespace AND typtype = 'e';"
            )
            enums = [row[0] for row in cursor.fetchall()]
            for enum in enums:
                cursor.execute(f'DROP TYPE IF EXISTS "{enum}" CASCADE;')

        self.stdout.write("Re-running all migrations...")
        call_command("migrate", "--no-input", verbosity=1)
