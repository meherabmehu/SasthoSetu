from datetime import date

from pydantic import BaseModel


class AppointmentReschedule(BaseModel):

    appointment_date: date

    appointment_time: str