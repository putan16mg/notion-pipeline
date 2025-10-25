#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CSV -> Notion 追加/補完スクリプト (_save版)
- 既存ページは「問題」「解答解説」のいずれかが空なら、その空欄だけ埋める（既存値は触らない）
- 両方とも埋まっている完全一致ペアはスキップ
- どちらにも該当しなければ新規作成
- 重複キーは Google Drive の fileId を使用（id=... / /d/... の両対応）
"""

import os, csv, re, time, json, unicodedata, sys
import requests
from typing import Dict, Tuple, Optional

# ===== 環境 =====
CSV_PATH = os.environ.get(
    "CSV_PATH",
    "/Users/odaakihisa/Documents/Notion_Auto/automation/data/ChatGPT_Merge_master.csv"
)
NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
NOTION_DB_ID = os.environ.get("NOTION_DB_ID", "")
DRY_RUN = os.environ.get("DRY_RUN", "0") == "1"
NOTION_VERSION = "2022-06-28"

# ===== ユーティリティ =====
REMOVALS = dict.fromkeys([0x00A0, 0x200B, 0xFEFF], None)
def nfc(s: str) -> str:
    if not isinstance(s, str): return s
    s = s.translate(REMOVALS)
    return unicodedata.normalize("NFC", s).strip()

re_id_qs   = re.compile(r"[?&]id=([^&/#]+)")
re_id_path = re.compile(r"/d/([^/]+)/?")
def drive_key(url: str) -> str:
    u = nfc(url or "")
    if not u: return ""
    m = re_id_qs.search(u)
    if m: return m.group(1)
    m = re_id_path.search(u)
    if m: return m.group(1)
    return u

def pair_key(p_url: str, a_url: str) -> Tuple[str, str]:
    return (drive_key(p_url), drive_key(a_url))

# ===== Notion REST =====
HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": NOTION_VERSION,
    "Content-Type": "application/json",
}
BASE = "https://api.notion.com/v1"

def ensure_env():
    if not NOTION_TOKEN:
        print("✖ NOTION_TOKEN 未設定", file=sys.stderr); sys.exit(2)
    if not NOTION_DB_ID:
        print("✖ NOTION_DB_ID 未設定", file=sys.stderr); sys.exit(2)

def fetch_existing_maps(db_id: str):
    pairs: Dict[Tuple[str,str], str] = {}
    by_p : Dict[str, Tuple[str,str,str]] = {}
    by_a : Dict[str, Tuple[str,str,str]] = {}

    has_more = True
    payload = {"page_size": 100}
    while has_more:
        r = requests.post(f"{BASE}/databases/{db_id}/query", headers=HEADERS, json=payload)
        r.raise_for_status()
        data = r.json()
        for page in data.get("results", []):
            pid = page["id"]
            props = page.get("properties", {})
            p_url = (props.get("問題") or {}).get("url") or ""
            a_url = (props.get("解答解説") or {}).get("url") or ""
            pk, ak = pair_key(p_url, a_url)
            pairs[(pk, ak)] = pid
            if pk: by_p[pk] = (pid, p_url, a_url)
            if ak: by_a[ak] = (pid, p_url, a_url)
        has_more = data.get("has_more", False)
        payload["start_cursor"] = data.get("next_cursor")
    return pairs, by_p, by_a

def create_page(db_id: str, row: Dict[str, str]) -> Optional[str]:
    year   = nfc(row.get("年度",""))
    subj   = nfc(row.get("科目",""))
    title  = nfc(row.get("タイトル","")) or "(無題)"
    p_url  = nfc(row.get("問題",""))
    a_url  = nfc(row.get("解答解説",""))
    kind   = nfc(row.get("種別",""))
    ptype  = nfc(row.get("問題の種類",""))

    payload = {
        "parent": {"database_id": db_id},
        "properties": {
            "タイトル": {"title": [{"type":"text","text":{"content": title}}]},
            "年度": {"number": int(year) if year.isdigit() else None},
            "科目": {"select": {"name": subj}} if subj else {"select": None},
            "問題": {"url": p_url or None},
            "解答解説": {"url": a_url or None},
            "種別": {"select": {"name": kind}} if kind else {"select": None},
            "問題の種類": {"select": {"name": ptype}} if ptype else {"select": None},
        },
    }
    if DRY_RUN:
        print(f"[DRY] create {title}")
        return "dry_page_id"
    r = requests.post(f"{BASE}/pages", headers=HEADERS, data=json.dumps(payload))
    if r.status_code >= 300:
        print(f"[WARN] create failed {r.status_code}: {r.text}")
        return None
    return r.json().get("id")

def patch_missing(page_id: str, want_p_url: str, want_a_url: str,
                  cur_p_url: str, cur_a_url: str) -> bool:
    props = {}
    if (not cur_p_url) and want_p_url:
        props["問題"] = {"url": want_p_url}
    if (not cur_a_url) and want_a_url:
        props["解答解説"] = {"url": want_a_url}

    if not props:
        return False

    payload = {"properties": props}
    if DRY_RUN:
        print(f"[DRY] patch {page_id} -> {list(props.keys())}")
        return True

    r = requests.patch(f"{BASE}/pages/{page_id}", headers=HEADERS, data=json.dumps(payload))
    if r.status_code >= 300:
        print(f"[WARN] patch failed {r.status_code}: {r.text}")
        return False
    return True

# ===== メイン処理 =====
def main():
    ensure_env()
    if not os.path.isfile(CSV_PATH):
        print(f"✖ CSVなし: {CSV_PATH}", file=sys.stderr); sys.exit(2)

    print("▶ Notion 既存ページ走査中…")
    pairs, by_p, by_a = fetch_existing_maps(NOTION_DB_ID)
    print(f"  既存ペア: {len(pairs)} / Pキー: {len(by_p)} / Aキー: {len(by_a)}")

    with open(CSV_PATH, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    print(f"▶ CSV読み込み: {len(rows)} 行")

    created = 0
    patched = 0
    skipped = 0

    for r in rows:
        p_url = nfc(r.get("問題",""))
        a_url = nfc(r.get("解答解説",""))
        pk, ak = pair_key(p_url, a_url)

        if any((pk, ak)) and (pk, ak) in pairs:
            skipped += 1
            continue

        if pk and pk in by_p:
            page_id, cur_p, cur_a = by_p[pk]
            if patch_missing(page_id, p_url, a_url, cur_p, cur_a):
                patched += 1
                new_p = cur_p or p_url
                new_a = cur_a or a_url
                pairs[(drive_key(new_p), drive_key(new_a))] = page_id
                by_p[pk] = (page_id, new_p, new_a)
            else:
                skipped += 1
            time.sleep(0.1)
            continue

        if ak and ak in by_a:
            page_id, cur_p, cur_a = by_a[ak]
            if patch_missing(page_id, p_url, a_url, cur_p, cur_a):
                patched += 1
                new_p = cur_p or p_url
                new_a = cur_a or a_url
                pairs[(drive_key(new_p), drive_key(new_a))] = page_id
                by_a[ak] = (page_id, new_p, new_a)
            else:
                skipped += 1
            time.sleep(0.1)
            continue

        pid = create_page(NOTION_DB_ID, r)
        if pid:
            created += 1
            npk, nak = pair_key(p_url, a_url)
            pairs[(npk, nak)] = pid
            if npk: by_p[npk] = (pid, p_url, a_url)
            if nak: by_a[nak] = (pid, p_url, a_url)
        time.sleep(0.1)

    print("✅ 完了")
    print(f"  新規作成: {created}")
    print(f"  既存補完: {patched}")
    print(f"  スキップ: {skipped}")
    print("▶ END")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[INTERRUPTED]"); sys.exit(130)
    except requests.HTTPError as e:
        print(f"[HTTPError] {e}"); sys.exit(1)
