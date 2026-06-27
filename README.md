# TezKhabar — News Website

## Setup

1. `pip install -r requirements.txt`
2. Firebase service account JSON values ko `app.py` mein FIREBASE_SA dict mein replace karo
3. ENV variables set karo:
   - `SUPER_ADMIN_EMAIL` — Super Admin ka email
   - `SUPER_ADMIN_PASSWORD` — Super Admin ka password

## Run

```bash
python app.py
# ya production ke liye:
gunicorn app:app
```

## Login

- **URL:** `https://tezkhabar-india.onrender.com`
- Super Admin + Admin + Editor — sab isi ek page se login karte hain

## Admin Roles

| Role | Access |
|---|---|
| Super Admin | Sab kuch — settings, user management, invites |
| Admin | Articles, team invite, image APIs |
| Editor | Sirf articles likho/edit karo |

## Image APIs

Admin Panel → Image APIs → ImgBB ya PostImage key add karo

## ENV Variables (Render/Railway)

```
SUPER_ADMIN_EMAIL=superadmin@tezkhabar.com
SUPER_ADMIN_PASSWORD=YourStrongPassword
PORT=5000
```

## Firebase Setup

1. Firebase Console → Project Settings → Service Accounts
2. Generate Private Key → JSON download karo
3. `app.py` mein FIREBASE_SA dict mein sab values paste karo
