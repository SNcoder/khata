# Site Khata — Material Management & Site Accounts

Python (Flask) backend + SQLite database + HTML/CSS/JavaScript frontend.

Modules:
1. **Dashboard** — godown/site stock, vendor outstanding, monthly summary, recent activity
2. **Material Tracking** — materials master, Purchase, Sale, Godown→Site Transfer (vehicle ke saath), Consumed, live stock (fully consumed = Nil), date/type filters
3. **Assets Tracking** — Purchase, Sale, Transfer, Consumed, location-wise register
4. **Labour Management** — labour register (type, site, contractor, Aadhaar, status), site/type/contractor/status filters, labour payments (Cash/Online/Bank Transfer/UPI/Cheque)
5. **Vendor Payments** — vendor master (contact person, GST, category, status), Goods Received (bills), Payments (mode + reference), Closing Balance, ledger filters
6. **Site Expenses** — Civil / Petrol / Diesel / Machinery Rent / Staff Salary / Other (Qty × Unit × Rate)
7. **Payment Register** — saare outgoing payments ek jagah (labour + vendor + expenses + purchases), filters + CSV export
8. **Receipt Register** — saare incoming payments, mode-wise summary, CSV export

---

## Chalane ka tarika (Windows / Mac / Linux)

### Step 1 — Python install karo (agar nahi hai)
https://www.python.org/downloads/ se Python 3.10+ install karo.
Windows par install karte waqt **"Add Python to PATH"** checkbox zaroor tick karo.

### Step 2 — Flask install karo
Folder ke andar terminal / command prompt kholo aur ye chalao:

    pip install -r requirements.txt

### Step 3 — App start karo

    python app.py

### Step 4 — Browser mein kholo

    http://localhost:5000

Bas! Pehla client add karo aur entries shuru karo.

---

## Password lagana (optional, deploy karne se pehle zaroori)

By default app bina login ke khulta hai (local use ke liye theek hai).
Password lagane ke liye app start karne se pehle environment variable set karo:

    # Windows (PowerShell)
    $env:APP_PASSWORD = "apna-password"
    python app.py

    # Mac / Linux
    APP_PASSWORD="apna-password" python app.py

Railway/Render par deploy karte waqt `APP_PASSWORD` ke saath `SECRET_KEY` bhi set karo
(koi bhi lambi random string) — warna har restart par sabko dobara login karna padega.
Login 30 din tak yaad rehta hai; sidebar ke neeche Logout button hai.

---

## Data kahan save hota hai?

Sab data **`database/khata.db`** file mein save hota hai (SQLite database).

- **Backup:** bas `database/khata.db` file ko copy karke pen drive / Google Drive mein rakh lo.
- **Restore:** wahi file wapas `database/` folder mein paste kar do.
- App band karne ya computer restart karne se data nahi jata.

## Office ke doosre computers se kaise use karein?

App start hone ke baad, usi network (same WiFi) ke kisi bhi computer/mobile se kholo:

    http://<aapke-computer-ka-IP>:5000

IP address jaanne ke liye: Windows par `ipconfig`, Mac/Linux par `ifconfig` chalao
(jaise `192.168.1.5` — to browser mein `http://192.168.1.5:5000` kholo).

## Files ka structure

    khata/
    ├── app.py                   → Entry point (`python app.py` se yahi chalta hai)
    ├── requirements.txt         → Python dependencies (sirf Flask)
    ├── backend/                 → Backend (Flask app + API routes)
    │   ├── __init__.py            → App factory (create_app), frontend serving, /health
    │   └── routes.py               → Saare /api/* routes (clients, sites, entries, vendors, expenses)
    ├── database/                → Database layer
    │   ├── connection.py          → SQLite/PostgreSQL connection, query helpers
    │   ├── schema.py               → Table definitions + init_db()
    │   └── khata.db                → SQLite data file (local runs; pehli baar chalane par ban jayega)
    └── frontend/                 → Frontend (static, served by Flask)
        ├── index.html              → Page structure (4 modules + client/site management)
        ├── style.css               → Design
        └── app.js                  → Frontend logic (API calls, rendering, forms)

## Aage kya add ho sakta hai

- Multi-user roles (site engineer vs account officer ke alag rights)
- Excel/PDF export of reports
- Bill ki photo upload
- Cloud hosting (taaki kahin se bhi khule) — Railway/Render par ₹0–500/month mein ho jata hai
