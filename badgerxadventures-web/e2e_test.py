"""End-to-end smoke test against the running Flask dev server."""
import json
import sys
import requests

BASE = "http://127.0.0.1:5055"
fails = []


def check(name, cond, extra=""):
    status = "OK" if cond else "FAIL"
    print(f"[{status}] {name} {extra}")
    if not cond:
        fails.append(name)


admin = requests.Session()
r = admin.post(f"{BASE}/api/admin/login", json={"email": "badger@example.com", "password": "testpassword123"})
check("admin login", r.status_code == 200, r.text)

r = admin.post(f"{BASE}/api/admin/codes", json={"pin_type": "stay", "label": "Test Cabin"})
check("admin generates code", r.status_code == 200, r.text)
code = r.json().get("code")
print("  generated code:", code)

r2 = admin.get(f"{BASE}/api/admin/codes")
check("admin list codes", r2.status_code == 200 and any(c["code"] == code for c in r2.json()))

owner = requests.Session()
r = owner.post(f"{BASE}/api/redeem", json={"code": code, "email": "owner1@example.com", "password": "ownerpass123"})
check("owner redeems code", r.status_code == 200, r.text)

r = owner.post(f"{BASE}/api/redeem", json={"code": code, "email": "owner1b@example.com", "password": "ownerpass123"})
check("code cannot be reused", r.status_code == 409, r.text)

r = owner.get(f"{BASE}/api/my-pin")
check("owner sees no pin yet", r.status_code == 200 and r.json()["pin"] is None, r.text)
check("owner's allowed type matches code", r.json()["allowed_pin_type"] == "stay")

r = owner.post(f"{BASE}/api/my-pin", json={"lat": 36.95, "lon": -84.95, "title": "Cedar Ridge Cabin", "phone": "555-1234"})
check("owner places pin", r.status_code == 200, r.text)

r = owner.post(f"{BASE}/api/my-pin", json={"lat": 36.9, "lon": -84.9, "title": "Second pin attempt"})
check("owner cannot place a second pin", r.status_code == 409, r.text)

r = owner.put(f"{BASE}/api/my-pin", json={"description": "A cozy lakeside cabin.", "events": "Live music Sat!",
                                           "availability": [{"from": "2026-10-01", "to": "2026-10-05"}]})
check("owner edits own pin", r.status_code == 200, r.text)

r = owner.get(f"{BASE}/api/my-pin")
mp = r.json()["pin"]
check("edit persisted", mp["description"] == "A cozy lakeside cabin." and mp["events"] == "Live music Sat!")
check("availability persisted", mp["availability"] == [{"from": "2026-10-01", "to": "2026-10-05"}])
my_pin_id = mp["id"]

# photo upload
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

# second owner / second code to test isolation
r = admin.post(f"{BASE}/api/admin/codes", json={"pin_type": "business", "label": "Test Business"})
code2 = r.json()["code"]
owner2 = requests.Session()
owner2.post(f"{BASE}/api/redeem", json={"code": code2, "email": "owner2@example.com", "password": "ownerpass456"})
owner2.post(f"{BASE}/api/my-pin", json={"lat": 36.9, "lon": -84.85, "title": "Joe's Bait Shop"})

r = owner2.get(f"{BASE}/api/my-pin")
check("owner2 sees their own pin, not owner1's", r.json()["pin"]["title"] == "Joe's Bait Shop")

r = owner2.put(f"{BASE}/api/my-pin", json={"description": "hijack attempt"})
r2 = owner.get(f"{BASE}/api/my-pin")
check("owner1's pin untouched by owner2's edit", r2.json()["pin"]["description"] == "A cozy lakeside cabin.")

# public map sees both pins
r = requests.get(f"{BASE}/api/pins")
titles = [p["title"] for p in r.json()]
check("public map lists both pins", "Cedar Ridge Cabin" in titles and "Joe's Bait Shop" in titles, titles)

# unauthenticated cannot touch owner endpoints
anon = requests.Session()
r = anon.get(f"{BASE}/api/my-pin")
check("anonymous blocked from /api/my-pin", r.status_code == 401)
r = anon.put(f"{BASE}/api/my-pin", json={"title": "nope"})
check("anonymous blocked from editing", r.status_code == 401)

# owner cannot use admin endpoints
r = owner.get(f"{BASE}/api/admin/pins")
check("owner blocked from admin API", r.status_code == 401)

# admin can edit/delete anyone's pin
r = admin.put(f"{BASE}/api/admin/pins/{my_pin_id}", json={"title": "Admin-edited title"})
check("admin can edit any pin", r.status_code == 200, r.text)
r = owner.get(f"{BASE}/api/my-pin")
check("admin's edit reflected", r.json()["pin"]["title"] == "Admin-edited title")

r = admin.delete(f"{BASE}/api/admin/pins/{my_pin_id}")
check("admin deletes a pin", r.status_code == 200, r.text)
r = owner.get(f"{BASE}/api/my-pin")
check("pin gone after admin delete, owner can place again", r.json()["pin"] is None)

r = owner.post(f"{BASE}/api/my-pin", json={"lat": 36.95, "lon": -84.95, "title": "Re-placed cabin"})
check("owner can place a new pin after admin deleted the old one", r.status_code == 200, r.text)

print()
if fails:
    print(f"{len(fails)} FAILURE(S):", fails)
    sys.exit(1)
else:
    print("ALL CHECKS PASSED")
