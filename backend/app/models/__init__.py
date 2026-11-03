"""Register all tables for migrations and standalone database tooling."""
from importlib import import_module

for _name in ('account_token', 'ai_feedback', 'appointment', 'care_consent', 'consultation', 'doctor', 'doctor_availability', 'file_record', 'hospital', 'medical_record', 'notification', 'patient', 'payment', 'prescription', 'prescription_item', 'rate_limit', 'provider', 'review', 'triage_session', 'user'):
    import_module(f"app.models.{_name}")
