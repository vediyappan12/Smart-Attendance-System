# Smart Attendance Management System

A full-stack attendance dashboard with a FastAPI API, MySQL persistence, employee management, check-in/check-out, CSV reports, and rule-based anomaly flags. Face verification is an optional add-on; the rest of the application works without face-recognition packages or biometric data.

## Features

- Employee directory with explicit, optional biometric consent.
- Separate employee kiosk and password-protected administrator dashboard.
- Daily check-in and check-out with duplicate/invalid action handling.
- Punctuality status using a configurable start time and grace period.
- Flags rapid re-entry and check-ins before 06:00 or at/after 22:00.
- Date-filtered attendance records, anomaly filtering, summary cards, and CSV export.
- Optional face matching. Uploaded images are processed in memory and not stored; enrolled face embeddings are encrypted using Fernet before database storage. Consent can be revoked through the API, which deletes the stored template.
- Responsive static frontend served by FastAPI.

## Requirements

- Python 3.10 or later
- MySQL 8.0 or compatible MariaDB server
- A modern browser; webcam access requires `localhost` or HTTPS

## Setup

### Quick start on Windows

From the project root in PowerShell:

```powershell
.\setup.ps1
.\start.ps1
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) for the employee kiosk. Open [http://127.0.0.1:8000/admin](http://127.0.0.1:8000/admin) for the separate administrator dashboard. The setup script creates a virtual environment and a local SQLite database so the application can run without MySQL credentials. The generated `.env` and database are ignored by Git.

The setup script creates a separate admin username and password; read them from `backend/.env` and enter them at `/admin`. The username defaults to `admin`. Admin sessions expire after eight hours and are kept in the current browser tab.

To stop the server, press **Ctrl+C** in the terminal running `start.ps1`. Do not use the old test URL `http://127.0.0.1:8765`; that was only a temporary static-file smoke-test server.

### Use MySQL

1. Create a database and restricted application account in MySQL:

   ```sql
   CREATE DATABASE attendance_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   CREATE USER 'attendance_user'@'127.0.0.1' IDENTIFIED BY 'choose-a-strong-password';
   GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, INDEX, ALTER ON attendance_db.* TO 'attendance_user'@'127.0.0.1';
   FLUSH PRIVILEGES;
   ```

2. Edit `backend/.env` and set `DATABASE_URL=` to blank, then configure `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, and `DB_NAME` for the MySQL account. Keep the generated `ADMIN_PASSWORD`, `ADMIN_API_KEY` signing secret, and `BIOMETRIC_ENCRYPTION_KEY` private and backed up. The settings file is loaded relative to the backend working directory.

3. Start the API and frontend together:

   ```powershell
   .\start.ps1
   ```

   API docs are available at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

   On first startup, SQLAlchemy creates the application's tables. Back up the database regularly. For production, use a schema migration tool and deploy behind HTTPS.

## Optional face recognition

On Windows, run the installer for the tested prebuilt dlib wheel (no Visual Studio build tools required):

```powershell
.\install-face-windows.ps1
```

The installer uses a prebuilt `dlib-bin` wheel and installs the face models and their Windows runtime dependencies. On other operating systems, activate the backend environment and install `requirements-face.txt`.

Generate a Fernet key and set it as `BIOMETRIC_ENCRYPTION_KEY` in `backend/.env`:

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Keep this key backed up separately and never commit it. The setup script creates a key if it is missing. Losing it makes existing face templates unusable.

After face recognition is installed and the server restarted, `/` enables employees to self-register, provide explicit consent, and enroll a face template in one step. The server creates a random employee code; the employee must keep it private for future face-verified check-in/check-out. A successful check-in displays “Attendance {name} added successfully.” Self-registration does not independently verify that a name or email belongs to an actual employee, so use this open kiosk only where self-enrollment is acceptable. Uploaded images are processed in memory and aren’t saved; face templates are encrypted before database storage. Administrators can revoke consent and erase an enrolled template through `DELETE /api/employees/{employee_code}/biometrics`.

## API overview

All employee and attendance APIs are private except the specific self-registration and face-verified attendance endpoints under `/api/public`. Admin endpoints require `Authorization: Bearer <admin-session-token>`, obtained from `POST /api/auth/login` using the `ADMIN_USERNAME` and `ADMIN_PASSWORD` in `backend/.env`. The OpenAPI documentation routes are available for development.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Health check |
| `POST` | `/api/auth/login` | Admin username/password login |
| `POST` | `/api/public/register` | Self-register and enroll an opted-in face |
| `POST` | `/api/public/attendance/check-in` | Face-verified employee check-in |
| `POST` | `/api/public/attendance/check-out` | Face-verified employee check-out |
| `GET` | `/api/employees` | List employees |
| `POST` | `/api/employees` | Create an employee |
| `POST` | `/api/employees/biometrics/enroll` | Enroll an opted-in employee's face template |
| `DELETE` | `/api/employees/{employee_code}/biometrics` | Revoke biometric consent and erase the template |
| `POST` | `/api/attendance/mark` | Record a check-in |
| `POST` | `/api/attendance/checkout` | Record a check-out |
| `GET` | `/api/reports` | Attendance report; accepts `start_date`, `end_date`, and `anomalies_only` |
| `GET` | `/api/reports/summary` | Today's dashboard totals |
| `GET` | `/api/reports/export.csv` | Download filtered report as CSV |
| `PATCH` | `/api/attendance/{record_id}` | Admin edit of attendance time, status, or anomaly notes |
| `DELETE` | `/api/attendance/{record_id}` | Admin deletion of an attendance record |

Example employee request:

```json
{
  "employee_code": "EMP-101",
  "full_name": "Alex Morgan",
  "email": "alex@example.com",
  "department": "Operations",
  "biometric_consent": false
}
```

Rapid repeat check-ins are controlled by the kiosk and repeat same-day check-ins are rejected. The admin dashboard supports editing or deleting records; restrict admin credentials to authorized staff and audit corrections.

## Production notes

- Terminate TLS at a trusted reverse proxy; do not expose the service over plain HTTP on an untrusted network.
- Keep a unique high-entropy token-signing secret and admin password, restrict database network access, and use a dedicated least-privilege SQL account.
- Keep the self-registration kiosk on a trusted network unless you add employment verification, rate limiting, and abuse monitoring. Face matching alone does not verify a claimed name or prove liveness.
- Keep the token-signing secret and generated admin password private; rotate them periodically. The current single-admin-account model is intended for a small trusted deployment, not multi-tenant access control.
- Open self-registration is not employee identity verification. If the kiosk is internet-accessible, add an invitation or employer identity-verification step, rate limiting, and abuse monitoring before production.
- Establish lawful basis, retention, access, and deletion policies before enabling biometric processing. Face embeddings are sensitive biometric data even when encrypted.
- `create_all` is convenient for initial setup; use managed migrations for updates to existing production schemas.
- Configure `CORS_ORIGINS` narrowly if hosting the frontend on a different origin.
