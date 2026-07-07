# Site Khata — Material Management & Site Accounts

Python (Flask) backend + SQLite database + HTML/CSS/JavaScript frontend.

Aapke handwritten note ke 4 modules:
1. **Material Tracking** — Purchase, Sale, Godown→Site / Site→Site Transfer, Consumed, Balance
2. **Assets Tracking** — Purchase, Sale, Transfer, Consumed, location-wise register
3. **Vendor Payments** — Goods Received (Site Engineer), Payment (Account Officer), Closing Balance
4. **Site Expenses** — Civil / Petrol / Diesel / Machinery Rent / Staff Salary / Other (Qty × Unit × Rate)

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

## Data kahan save hota hai?

Sab data isi folder mein **`khata.db`** file mein save hota hai (SQLite database).

- **Backup:** bas `khata.db` file ko copy karke pen drive / Google Drive mein rakh lo.
- **Restore:** wahi file wapas folder mein paste kar do.
- App band karne ya computer restart karne se data nahi jata.

## Office ke doosre computers se kaise use karein?

App start hone ke baad, usi network (same WiFi) ke kisi bhi computer/mobile se kholo:

    http://<aapke-computer-ka-IP>:5000

IP address jaanne ke liye: Windows par `ipconfig`, Mac/Linux par `ifconfig` chalao
(jaise `192.168.1.5` — to browser mein `http://192.168.1.5:5000` kholo).

## Files ka structure

    site-khata/
    ├── app.py              → Backend (Python/Flask) + database logic
    ├── requirements.txt    → Python dependencies (sirf Flask)
    ├── khata.db            → Database (pehli baar chalane par ban jayega)
    └── static/
        ├── index.html      → Frontend page
        ├── style.css       → Design
        └── app.js          → Frontend logic (API calls, rendering)

## Aage kya add ho sakta hai

- Login / users (site engineer vs account officer ke alag rights)
- Excel/PDF export of reports
- Bill ki photo upload
- Cloud hosting (taaki kahin se bhi khule) — Railway/Render par ₹0–500/month mein ho jata hai
