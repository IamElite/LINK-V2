import os, sys, zipfile, shutil, tempfile, subprocess
from urllib import request
from datetime import datetime, timezone

os.environ["TZ"] = "Asia/Kolkata"
try:
    import time
    time.tzset()
except:
    pass

def ts():
    return datetime.now(timezone.utc).astimezone().strftime("%d-%b-%y %H:%M:%S")

UPSTREAM_REPO = os.environ.get("UPSTREAM_REPO", "https://github.com/IamElite/LINK-V2")
UPSTREAM_BRANCH = os.environ.get("UPSTREAM_BRANCH", "kartik")

def update_from_repo():
    now = ts()
    clean_repo = UPSTREAM_REPO.rstrip("/")
    if clean_repo.endswith(".git"):
        clean_repo = clean_repo[:-4]

    zip_url = f"{clean_repo}/archive/refs/heads/{UPSTREAM_BRANCH}.zip"
    print(f"[{now}] [UPDATE] Fetching {UPSTREAM_BRANCH}...")

    with tempfile.TemporaryDirectory() as tmp:
        zip_path = os.path.join(tmp, "update.zip")
        extract_path = os.path.join(tmp, "extracted")
        os.makedirs(extract_path)

        try:
            request.urlretrieve(zip_url, zip_path)
        except Exception as e:
            print(f"[{now}] [UPDATE FAIL] {e}")
            return False

        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(extract_path)

        root_folder = os.listdir(extract_path)[0]
        root_path = os.path.join(extract_path, root_folder)

        skip = {".git", "__pycache__", ".env"}

        for item in os.listdir(root_path):
            if item in skip:
                continue
            s = os.path.join(root_path, item)
            d = os.path.join(".", item)
            if os.path.isdir(s):
                if os.path.exists(d):
                    shutil.rmtree(d)
                shutil.move(s, d)
            else:
                if os.path.exists(d):
                    os.remove(d)
                shutil.move(s, d)

    if os.path.exists("requirements.txt"):
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "--quiet"],
            capture_output=True, text=True
        )
        installed = [l for l in result.stdout.split("\n") if "Successfully installed" in l]
        msg = installed[0].replace("Successfully installed ", "") if installed else "requirements satisfied"
        print(f"[{now}] [UPDATE] Updated! {msg}")
    else:
        print(f"[{now}] [UPDATE] Updated! (no requirements)")

    return True

if __name__ == "__main__":
    update_from_repo()
