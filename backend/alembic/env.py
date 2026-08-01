from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import settings
# Every model module must be imported here or autogenerate will treat its
# tables as absent from the metadata and propose dropping them. Ordered so
# that a table is registered before anything referencing it.
from app.models.base import Base
from app.models.user import User
from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.doctor_availability import DoctorAvailability
from app.models.appointment import Appointment
from app.models.prescription import Prescription
from app.models.medical_record import MedicalRecord
from app.models.file_record import FileRecord
from app.models.notification import Notification
from app.models.ai_feedback import AIFeedback


# Imports above register every model with Base.metadata for autogeneration.
_MODELS = (
    AIFeedback,
    Appointment,
    Doctor,
    DoctorAvailability,
    FileRecord,
    MedicalRecord,
    Notification,
    Patient,
    Prescription,
    User,
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

database_url = config.attributes.get("database_url", settings.database_url)
config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()