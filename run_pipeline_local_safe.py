#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, subprocess, sys

# === 共通設定 ===
CSV_PATH_LOCAL = "/Users/odaakihisa/Documents/Notion_Auto/automation/data/ChatGPT_Merge_master.csv"
CDIR_LOCAL = "/Users/odaakihisa/Documents/Notion_Auto/automation"

# === GitHub Actions用 ===
CSV_PATH_CI = os.path.join(os.getcwd(), "data/ChatGPT_Merge_master.csv")
CDIR_CI = os.getcwd()

# === 実行環境を判定 ===
if os.environ.get("GITHUB_ACTIONS", "") == "true":
    CSV_PATH = CSV_PATH_CI
    CDIR = CDIR_CI
else:
    CSV_PATH = CSV_PATH_LOCAL
    CDIR = CDIR_LOCAL

NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
NOTION_DB_ID = os.environ.get("NOTION_DB_ID")
DRY_RUN = os.environ.get("DRY_RUN", "False").lower() in ("1", "true")

def run(cmd):
    print(">>>", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)

def main():
    if not NOTION_TOKEN or not NOTION_DB_ID:
        print("⚠️ NOTION_TOKEN または NOTION_DB_ID が設定されていません。")
        sys.exit(1)

    os.environ["NOTION_TOKEN"] = NOTION_TOKEN
    os.environ["NOTION_DB_ID"] = NOTION_DB_ID
    os.environ["CSV_PATH"] = CSV_PATH
    if DRY_RUN:
        os.environ["DRY_RUN"] = "1"
    else:
        os.environ.pop("DRY_RUN", None)

    os.chdir(CDIR)
    print(f"📂 現在の作業ディレクトリ: {CDIR}")

    print("=== [1/2] AppendCSV_New ===")
    run(["python3", "run_all_append_csv_new.py"])

    print("=== [2/2] Notion Upsert ===")
    run(["python3", "notion_upsert_from_csv.py"])

    print("✅ DONE")

if __name__ == "__main__":
    main()

