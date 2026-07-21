# 🩺 SasthoSetu – AI-Powered Healthcare Platform

SasthoSetu is a modern healthcare platform built with **FastAPI**, **PostgreSQL**, and **SQLAlchemy**. It provides secure APIs for patient management, doctor scheduling, appointments, medical records, prescriptions, notifications, and an AI-assisted symptom checker.

---

# 📌 Project Overview

SasthoSetu aims to simplify healthcare services by providing a centralized backend platform for hospitals, clinics, doctors, and patients.

The platform follows a modular architecture with secure authentication, scalable REST APIs, and database migration support using Alembic.

---

# ✨ Features

- 🩺 AI-Assisted Symptom Checker
- 👨‍⚕️ Doctor Management
- 👤 Patient Management
- 📅 Appointment Scheduling
- ⏰ Doctor Availability & Slot Management
- 🏥 Hospital Management
- 💊 Prescription Management
- 📂 Medical Records
- 📁 File Upload Support
- 🔔 Notification System
- 📊 Dashboard APIs
- 🔐 JWT Authentication & Authorization
- 🗄️ Database Migration using Alembic

---

# 🛠 Tech Stack

## Backend

- Python
- FastAPI

## Database

- PostgreSQL
- SQLAlchemy
- Alembic

## Authentication

- JWT
- OAuth2

## Development Tools

- Uvicorn
- Git
- GitHub

---

# 📂 Project Structure

```text
SasthoSetu/
│
├── backend/
│   ├── app/
│   │   ├── core/
│   │   ├── models/
│   │   ├── modules/
│   │   ├── schemas/
│   │   └── main.py
│   │
│   ├── alembic/
│   ├── tests/
│   ├── requirements.txt
│   └── .env.example
│
├── docs/
├── scripts/
├── README.md
└── .gitignore
```

---

# 🔄 System Architecture

```text
Patient / Doctor
        │
        ▼
 FastAPI REST API
        │
        ▼
Authentication Layer
        │
        ▼
Business Logic Modules
        │
        ▼
SQLAlchemy ORM
        │
        ▼
PostgreSQL Database
```

---

# 🧩 Core Modules

- Authentication
- Patients
- Doctors
- Doctor Availability
- Appointment Management
- Medical Records
- Prescriptions
- Notifications
- Dashboard
- Patient History
- Symptom Checker
- File Management

---

# 🚀 Installation

Clone the repository

```bash
git clone https://github.com/meherabmehu/SasthoSetu.git
```

Move into the backend

```bash
cd SasthoSetu/backend
```

Create a virtual environment

```bash
python -m venv .venv
```

Activate it

### Windows

```bash
.venv\Scripts\activate
```

### Linux / macOS

```bash
source .venv/bin/activate
```

Install dependencies

```bash
pip install -r requirements.txt
```

Configure environment variables

```bash
cp .env.example .env
```

Run database migrations

```bash
alembic upgrade head
```

Start the development server

```bash
uvicorn app.main:app --reload
```

---

# 📖 API Documentation

After starting the server:

### Swagger UI

```text
http://127.0.0.1:8000/docs
```

### ReDoc

```text
http://127.0.0.1:8000/redoc
```

---

# 🧪 Running Tests

```bash
python -m unittest discover -s tests -v
```

---

# 🚀 Future Improvements

- AI Disease Prediction
- Medical Image Analysis
- LLM-powered Health Assistant
- Telemedicine Integration
- Electronic Health Record (EHR) Support
- Docker Deployment
- CI/CD Pipeline
- Cloud Deployment

---

# 👨‍💻 Author

**Md. Meherab Hossain Talukder**

- GitHub: https://github.com/meherabmehu
- LinkedIn: https://www.linkedin.com/in/meherab-talukder-5046a141b/
- Kaggle: https://www.kaggle.com/mdmeherabhossain

---

# 📄 License

This project is licensed under the MIT License.
