# -*- coding: utf-8 -*-
"""
ChatGPT作成問題のローカル/Driveファイルを走査し、
(年度, 日付, 科目, Q番号) の4点キーで「問題」と「解答」をペアリング。
既存CSVを上書きせず、新規データのみ追記（Append）。
Google Drive のリンクは、サービスアカウント認証で検索して補完（同意画面なし）。

★変更点（最小）：
- READ_FROM_DRIVE/DRIVE_ROOT_ID フラグ追加（環境変数）
- Drive配下の .txt をAPIで一時ダウンロードする関数を追加（フラグONの時だけ）
- SCOPES を read-only に拡張（ダウンロードのため）
- 既存ロジックはそのまま（collect_and_pair_files → process_and_output_csv）
"""

import os
import re
import csv
import unicodedata
from datetime import datetime
from collections import defaultdict
from typing import Dict, Tuple, Optional, List, Set

# ====== 固定/環境パス ======
ROOT_DIR = os.environ.get(
    "ROOT_DIR",
    "/Users/odaakihisa/Library/CloudStorage/GoogleDrive-radioheadsyrup16g@gmail.com/マイドライブ/診断士試験/一次試験/問題・演習/chat gpt作成問題"
)
LOG_DIR  = os.environ.get("LOG_DIR", "/Users/odaakihisa/Library/CloudStorage/GoogleDrive-radioheadsyrup16g@gmail.com/マイドライブ/診断士試験/一次試験/_logs")
CSV_OUT  = os.environ.get("CSV_PATH", "/Users/odaakihisa/Documents/Notion_Auto/automation/data/ChatGPT_Merge_master.csv")
BAK_PATH = CSV_OUT + ".bak"

# Drive ルート（あなたが渡したフォルダID）
DRIVE_ROOT_ID = os.environ.get("DRIVE_ROOT_ID", "1XL-9dP0ToNj5MgAMCEPqGH52rUYSciWK")

# サービスアカウントJSON（環境変数優先）
SERVICE_ACCOUNT_FILE = os.environ.get(
    "SERVICE_ACCOUNT_FILE",
    "/Users/odaakihisa/Documents/Notion_Auto/automation/notionauto-474307-50e14130c274.json"
)

# ========= 検索ルール =========
ROLE_BY_FOLDER = {"問題": "problem", "答案解説": "answer"}
SUBJ_MAP = {
    "財務": "財務会計", "財務会計": "財務会計",
    "経済": "経済学", "経済学": "経済学",
    "法務": "法務", "経営法務": "法務",
    "情報": "情報", "経営情報システム": "情報"
}
Q_RE    = re.compile(r"(?:^|_)Q(\d{1,2})(?:_|$)", re.IGNORECASE)
DATE_RE = re.compile(r"(\d{4})_(\d{4})")

# ====== Drive（サービスアカウント認証。OAuth同意画面なし） ======
from google.oauth2 import service_account
from googleapiclient.discovery import build

# ★変更点：ダウンロードを伴うため read-only 権限に拡張
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

# ★変更点：Drive直読みのON/OFF（既定はOFF＝ローカル走査）
READ_FROM_DRIVE = os.environ.get("READ_FROM_DRIVE", "0") == "1"
# ★変更点：Driveの一時展開先
DRIVE_CACHE_DIR = os.path.join(os.getcwd(), ".drive_cache")

def build_drive_service():
    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        raise FileNotFoundError(f"[FATAL] サービスアカウントが無い: {SERVICE_ACCOUNT_FILE}")
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    svc = build("drive", "v3", credentials=creds, cache_discovery=False)
    print("✅ Drive(Service Account) OK（同意画面なし）")
    return svc

def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s or "")

def norm_subject(name: str) -> Optional[str]:
    if not name: return None
    return SUBJ_MAP.get(name.strip(), name.strip())

def parse_meta_from_path(path: str) -> Optional[Tuple[str, str, str]]:
    m = DATE_RE.search(path)
    if not m: return None
    year, mmdd = m.group(1), m.group(2)
    q = "Q??"
    mq = Q_RE.search(os.path.basename(path))
    if mq: q = f"Q{int(mq.group(1)):02d}"
    return (year, mmdd, q)

def guess_role_by_path(path: str) -> Optional[str]:
    for p in path.split(os.sep):
        if p in ROLE_BY_FOLDER: return ROLE_BY_FOLDER[p]
    return None

def build_title_from_problem_path(problem_path: str) -> str:
    base = os.path.splitext(os.path.basename(problem_path))[0]
    return base

def walk_files(root: str):
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            if fn.lower().endswith(".txt"):
                yield os.path.join(dirpath, fn)

def collect_and_pair_files(root_dir: str):
    print("▶ ファイル収集開始...")
    items: Dict[Tuple[str, str, str, str], Dict[str, str]] = defaultdict(dict)
    for path in walk_files(root_dir):
        role = guess_role_by_path(path)
        if role not in ("problem", "answer"): continue
        rel = os.path.relpath(path, root_dir)
        parts = rel.split(os.sep)
        subj = norm_subject(parts[0] if parts else "")
        if not subj: continue
        meta = parse_meta_from_path(path)
        if not meta: continue
        year, mmdd, qno = meta
        key = (year, mmdd, subj, qno)
        items[key].setdefault("problem", "")
        items[key].setdefault("answer", "")
        items[key][role] = path
    print(f"▶ 収集完了: {len(items)}件")
    return items

def make_uid(year: str, mmdd: str, subj: str, qno: str) -> str:
    return f"{year}-{mmdd}-{subj}-{qno}"

def read_existing_uids(csv_path: str) -> Set[str]:
    uids = set()
    if not os.path.exists(csv_path): return uids
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            uid = row.get("外部UID")
            if not uid:
                y, d, s, q = row.get("年度",""), row.get("日付",""), row.get("科目",""), row.get("Q番号","")
                if y and d and s and q:
                    uid = make_uid(y, d, s, q)
            if uid:
                uids.add(uid)
    return uids

# ====== ★ここだけ最小修正（それ以外は一切変更なし） ======
def resolve_drive_url_by_local_path(drive, drive_root_id, local_path, root_dir):
    """ローカルのベース名でDrive検索 → 親フォルダ名一致スコアで最適1件 → webViewLink"""
    if not local_path:
        return ""
    # ★ 追加：NFC 正規化（macとubuntuの文字コード差を吸収）
    base = nfc(os.path.basename(local_path))

    # ★ 修正点1：完全一致から部分一致に変更（name = → name contains）
    res = drive.files().list(
        q=f"name contains '{base}' and trashed = false",
        fields="files(id,name,parents,webViewLink)",
        pageSize=50,
        includeItemsFromAllDrives=True,
        supportsAllDrives=True,
    ).execute()
    files = res.get("files", [])

    if not files:
        return ""

    rel = os.path.relpath(local_path, root_dir)
    local_dirs = [nfc(x) for x in rel.split(os.sep)[:-1]]

    parent_cache = {}
    def get_first_parent_name(file):
        parents = file.get("parents") or []
        if not parents:
            return ""
        pid = parents[0]
        if pid in parent_cache:
            return parent_cache[pid]
        meta = drive.files().get(
            fileId=pid,
            fields="id,name,parents",
            supportsAllDrives=True
        ).execute()
        parent_cache[pid] = meta.get("name","")
        return parent_cache[pid]

    best, best_score = None, -1
    for f in files:
        pname = nfc(get_first_parent_name(f))
        score = 0
        if local_dirs:
            last_local = local_dirs[-1]
            if pname == last_local:
                score += 2
            elif pname.lower() == last_local.lower():
                score += 1
        if score > best_score:
            best, best_score = f, score

    if not best:
        return ""
    # ★ 修正点2：URL取得の冗長化（保険）
    return best.get("webViewLink") or f"https://drive.google.com/open?id={best['id']}&usp=drive_fs"
# ====== ★最小修正ここまで ======

# ===★ 追加：Drive直読み用（フラグON時のみ使用）★===
import io  # ★変更点
from googleapiclient.http import MediaIoBaseDownload  # ★変更点

def iter_drive_children(drive, folder_id):
    page_token = None
    while True:
        resp = drive.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            fields="nextPageToken, files(id, name, mimeType, webViewLink)",
            pageSize=1000,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            pageToken=page_token,
        ).execute()
        for f in resp.get("files", []):
            yield f
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

def materialize_drive_txts(drive, root_id, out_root):
    """DriveのfolderId配下を再帰探索して .txt を out_root に保存"""
    if not root_id:
        print("⚠ DRIVE_ROOT_ID 未設定（READ_FROM_DRIVE=1なのに）"); return 0
    os.makedirs(out_root, exist_ok=True)
    created = 0
    queue = [(root_id, "")]
    while queue:
        fid, rel = queue.pop(0)
        for f in iter_drive_children(drive, fid):
            name = nfc(f["name"])
            if f["mimeType"] == "application/vnd.google-apps.folder":
                queue.append((f["id"], os.path.join(rel, name)))
                continue
            if not name.lower().endswith(".txt"):
                continue
            dst_dir = os.path.join(out_root, rel)
            os.makedirs(dst_dir, exist_ok=True)
            dst = os.path.join(dst_dir, name)
            req = drive.files().get_media(fileId=f["id"], supportsAllDrives=True)
            with io.FileIO(dst, "wb") as fh:
                downloader = MediaIoBaseDownload(fh, req)
                done = False
                while not done:
                    _, done = downloader.next_chunk()
            created += 1
    return created
# ===★ ここまで追加★===


# ===★ ここから既存（CSV改行保証）★===
def ensure_trailing_newline(path: str):
    """既存CSVの末尾に改行が無ければ補う"""
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return
    with open(path, "rb") as f:
        f.seek(-1, os.SEEK_END)
        last = f.read(1)
    if last not in (b"\n", b"\r"):
        with open(path, "ab") as f:
            f.write(b"\n")
# ===★ ここまで既存★===

def process_and_output_csv(items, csv_out, log_dir):
    os.makedirs(os.path.dirname(csv_out), exist_ok=True)
    os.makedirs(log_dir, exist_ok=True)
    nowstamp = datetime.now().strftime("%Y%m%d_%H%M")
    log_path = os.path.join(log_dir, f"build_log_{nowstamp}.txt")

    headers = [
        "年度", "日付", "Q番号", "科目", "タイトル",
        "問題", "解答解説", "種別", "問題の種類",
        "ローカルパス(問題)", "ローカルパス(解答)", "外部UID",
    ]

    existing_uids = read_existing_uids(csv_out)
    print(f"▶ 既存UID数: {len(existing_uids)}")

    drive = build_drive_service()

    new_rows: List[List[str]] = []
    for (year, mmdd, subj, qno), rec in sorted(items.items()):
        uid = make_uid(year, mmdd, subj, qno)
        if uid in existing_uids:
            continue  # 追記のみ

        prob_path = rec.get("problem", "")
        ans_path  = rec.get("answer",  "")
        title = build_title_from_problem_path(prob_path) if prob_path else ""
        type1, kind = "問題", "ChatGPT問題"

        # Drive検索でリンク補完
        prob_url = resolve_drive_url_by_local_path(drive, DRIVE_ROOT_ID, prob_path, (DRIVE_CACHE_DIR if READ_FROM_DRIVE else ROOT_DIR))
        ans_url  = resolve_drive_url_by_local_path(drive, DRIVE_ROOT_ID,  ans_path, (DRIVE_CACHE_DIR if READ_FROM_DRIVE else ROOT_DIR))

        new_rows.append([
            year, mmdd, qno, subj, title,
            prob_url, ans_url, type1, kind,
            prob_path, ans_path, uid
        ])

    if new_rows:
        write_header = not os.path.exists(csv_out) or os.path.getsize(csv_out) == 0
        ensure_trailing_newline(csv_out)
        with open(csv_out, "a", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            if write_header:
                w.writerow(headers)
            w.writerows(new_rows)
        print(f"✅ {len(new_rows)}件を追記しました → {csv_out}")
    else:
        print("▶ 新規データなし（追記ゼロ）")

    with open(log_path, "w", encoding="utf-8") as lg:
        lg.write(f"{datetime.now().isoformat()} に完了\n")
    print(f"📝 ログ: {log_path}")
    print("▶ END")

def main():
    # ★追加：Drive直読みがONなら .txt を一時取得してから既存ロジックで走査
    if READ_FROM_DRIVE:
        drive = build_drive_service()
        print("▶ DriveからTXTを取得（キャッシュ展開）...")
        n = materialize_drive_txts(drive, DRIVE_ROOT_ID, DRIVE_CACHE_DIR)
        print(f"▶ Drive取得完了: {n} 件")
        use_root = DRIVE_CACHE_DIR
    else:
        use_root = ROOT_DIR

    items = collect_and_pair_files(use_root)
    process_and_output_csv(items, CSV_OUT, LOG_DIR)

if __name__ == "__main__":
    main()
