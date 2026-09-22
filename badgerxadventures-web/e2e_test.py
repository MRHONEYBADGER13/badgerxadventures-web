"""End-to-end smoke test against the running Flask dev server. Exercises the
whole themed-map backend: invite codes, owner signup, placing a pin (fixed
x/y location), editing everything except the location, the admin's full
override (including moving a pin), and permission boundaries.

Run with the dev server up: `python3 app.py` in one terminal, then
`python3 e2e_test.py` in another. Needs an admin account first:
`python3 seed_admin.py admin@example.com somepassword`.
"""
import sys
import requests

BASE = "http://127.0.0.1:5055"
ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "somepassword"
fails = []


def check(name, cond, extra=""):
    status = "OK" if cond else "FAIL"
    print(f"[{status}] {name} {extra}")
    if not cond:
        fails.append(name)


admin = requests.Session()
r = admin.post(f"{BASE}/api/admin/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
check("admin login", r.status_code == 200, r.text)

# ---------- invite codes ----------

r = admin.post(f"{BASE}/api/admin/codes", json={"pin_type": "stay", "label": "Test Cabin"})
check("admin generates a stay code", r.status_code == 200, r.text)
stay_code = r.json().get("code")

r = admin.post(f"{BASE}/api/admin/codes", json={"pin_type": "business", "label": "Test Business"})
business_code = r.json().get("code")

r = admin.post(f"{BASE}/api/admin/codes", json={"pin_type": "custom", "label": "Test Landmark"})
custom_code = r.json().get("code")

r2 = admin.get(f"{BASE}/api/admin/codes")
check("admin list codes", r2.status_code == 200 and any(c["code"] == stay_code for c in r2.json()))

# ---------- owner: a stay ----------

owner = requests.Session()
r = owner.post(f"{BASE}/api/redeem", json={"code": stay_code, "email": "owner1@example.com", "password": "ownerpass123"})
check("owner redeems a stay code", r.status_code == 200, r.text)

r = owner.post(f"{BASE}/api/redeem", json={"code": stay_code, "email": "owner1b@example.com", "password": "ownerpass123"})
check("code cannot be reused", r.status_code == 409, r.text)

r = owner.get(f"{BASE}/api/my-pin")
check("owner sees no pin yet", r.status_code == 200 and r.json()["pin"] is None, r.text)
check("owner's allowed type matches code", r.json()["allowed_pin_type"] == "stay")

r = owner.post(f"{BASE}/api/my-pin", json={
    "x": 0.42, "y": 0.55, "title": "Cedar Ridge Cabin", "type": "cabin",
    "phone": "555-1234", "price": 180, "sleeps": 6,
})
check("owner places a stay pin", r.status_code == 200, r.text)
stay_id = r.json()["id"]

r = owner.post(f"{BASE}/api/my-pin", json={"x": 0.1, "y": 0.1, "title": "Second pin attempt"})
check("owner cannot place a second pin", r.status_code == 409, r.text)

r = owner.put(f"{BASE}/api/my-pin", json={
    "description": "A cozy lakeside cabin.", "events": "Live music Sat!",
    "availability": [{"from": "2026-10-01", "to": "2026-10-05"}],
})
check("owner edits own pin's info", r.status_code == 200, r.text)

r = owner.put(f"{BASE}/api/my-pin", json={"x": 0.99, "y": 0.99, "description": "trying to move it"})
check("owner's attempt to move their own pin is a no-op (not rejected, just ignored)", r.status_code == 200, r.text)

r = owner.get(f"{BASE}/api/my-pin")
mp = r.json()["pin"]
check("info edit persisted", mp["desc"] == "trying to move it")
check("location NEVER moved by the owner's edit", mp["x"] == 0.42 and mp["y"] == 0.55, (mp["x"], mp["y"]))
check("availability persisted", mp["avail"] == [{"from": "2026-10-01", "to": "2026-10-05"}])

# ---------- photo upload ----------

from PIL import Image
import io
buf = io.BytesIO()
Image.new("RGB", (400, 300), (200, 100, 50)).save(buf, "JPEG")
buf.seek(0)
r = owner.post(f"{BASE}/api/my-pin/photos", files={"photo": ("test.jpg", buf, "image/jpeg")})
check("owner uploads a photo", r.status_code == 200, r.text)
photo_path = r.json()["photos"][0] if r.status_code == 200 else None
if photo_path:
    r = requests.get(BASE + photo_path)
    check("uploaded photo is servable", r.status_code == 200 and r.headers["content-type"].startswith("image"))
    r = owner.delete(f"{BASE}/api/my-pin/photos", json={"path": photo_path})
    check("owner removes their own photo", r.status_code == 200 and r.json()["photos"] == [], r.text)

# ---------- owner: a business (isolation from the stay owner) ----------

owner2 = requests.Session()
owner2.post(f"{BASE}/api/redeem", json={"code": business_code, "email": "owner2@example.com", "password": "ownerpass456"})
r = owner2.post(f"{BASE}/api/my-pin", json={"x": 0.3, "y": 0.2, "title": "Joe's Bait Shop", "cat": "fishing"})
check("owner2 places a business pin", r.status_code == 200, r.text)

r = owner2.get(f"{BASE}/api/my-pin")
check("owner2 sees their own pin, not owner1's", r.json()["pin"]["title"] == "Joe's Bait Shop")

owner2.put(f"{BASE}/api/my-pin", json={"description": "hijack attempt"})
r2 = owner.get(f"{BASE}/api/my-pin")
check("owner1's pin untouched by owner2's edit", r2.json()["pin"]["desc"] == "trying to move it")

# ---------- owner: a custom pin ----------

owner3 = requests.Session()
owner3.post(f"{BASE}/api/redeem", json={"code": custom_code, "email": "owner3@example.com", "password": "ownerpass789"})
r = owner3.post(f"{BASE}/api/my-pin", json={"x": 0.6, "y": 0.6, "title": "Trailhead Marker", "cat": "custom"})
check("owner3 places a custom pin", r.status_code == 200, r.text)

# ---------- public map ----------

r = requests.get(f"{BASE}/api/pins")
data = r.json()
pin_titles = [p["title"] for p in data["pins"]]
stay_titles = [p["title"] for p in data["stays"]]
check("public map lists the business and custom pins", "Joe's Bait Shop" in pin_titles and "Trailhead Marker" in pin_titles, pin_titles)
check("public map lists the stay separately", "Cedar Ridge Cabin" in stay_titles, stay_titles)

# ---------- permission boundaries ----------

anon = requests.Session()
r = anon.get(f"{BASE}/api/my-pin")
check("anonymous blocked from /api/my-pin", r.status_code == 401)
r = anon.put(f"{BASE}/api/my-pin", json={"title": "nope"})
check("anonymous blocked from editing", r.status_code == 401)

r = owner.get(f"{BASE}/api/admin/pins")
check("owner blocked from admin API", r.status_code == 401)

# ---------- admin: full override, including moving a pin ----------

r = admin.put(f"{BASE}/api/admin/pins/{stay_id}", json={"title": "Admin-edited title"})
check("admin can edit any pin's info", r.status_code == 200, r.text)
r = owner.get(f"{BASE}/api/my-pin")
check("admin's info edit reflected", r.json()["pin"]["title"] == "Admin-edited title")

r = admin.put(f"{BASE}/api/admin/pins/{stay_id}", json={"x": 0.77, "y": 0.33})
check("admin CAN move a pin (only the admin can)", r.status_code == 200, r.text)
r = owner.get(f"{BASE}/api/my-pin")
check("admin's move reflected", (r.json()["pin"]["x"], r.json()["pin"]["y"]) == (0.77, 0.33))

r = admin.delete(f"{BASE}/api/admin/pins/{stay_id}")
check("admin deletes a pin", r.status_code == 200, r.text)
r = owner.get(f"{BASE}/api/my-pin")
check("pin gone after admin delete, owner can place again", r.json()["pin"] is None)

r = owner.post(f"{BASE}/api/my-pin", json={"x": 0.5, "y": 0.5, "title": "Re-placed cabin", "type": "cabin"})
check("owner can place a new pin after admin deleted the old one", r.status_code == 200, r.text)

# ---------- weather endpoint always returns something shaped correctly ----------

r = requests.get(f"{BASE}/api/weather")
wx = r.json()
check("weather endpoint responds with the expected shape", r.status_code == 200 and "places" in wx and isinstance(wx["places"], list), wx)

print()
if fails:
    print(f"{len(fails)} FAILURE(S):", fails)
    sys.exit(1)
else:
    print("ALL CHECKS PASSED")
