#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, subprocess, sys

# === 設定値：環境変数優先（ローカル/CI両対応） ===
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
NOTION_DB_ID = os.environ.get("NOTION_DB_ID")
CSV_PATH = os.environ.get("CSV_PATH", os.path.join(os.getcwd(), "ChatGPT_Merge_master.csv"))
LOG_DIR  = os.environ.get("LOG_DIR",  os.path.join(os.getcwd(), "logs"))
SERVICE_ACCOUNT_FILE = os.environ.get("SERVICE_ACCOUNT_FILE", "")

# Drive直読み（CI時のみONでOK。ローカルは未設定のままでよい）
READ_FROM_DRIVE = os.environ.get("READ_FROM_DRIVE", "0").lower() in ("1", "true")
DRIVE_ROOT_ID   = os.environ.get("DRIVE_ROOT_ID", "")

DRY_RUN = os.environ.get("DRY_RUN", "0").lower() in ("1", "true")

def run(cmd):
    print(">>>", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)

def main():
    print(f"📂 現在の作業ディレクトリ: {os.getcwd()}")
    print(f"🗂 参照CSV: {CSV_PATH}")
    print(f"🗒 ログ出力先: {LOG_DIR}")
    if READ_FROM_DRIVE:
        print(f"🌐 READ_FROM_DRIVE=1 / DRIVE_ROOT_ID={DRIVE_ROOT_ID[:8]}...")

    # 必須チェック（CIでの人的ミスを早期検出）
    if not NOTION_TOKEN or not NOTION_DB_ID:
        print("✖ NOTION_TOKEN / NOTION_DB_ID が未設定です", file=sys.stderr); sys.exit(2)
    if READ_FROM_DRIVE and not SERVICE_ACCOUNT_FILE:
        print("✖ SERVICE_ACCOUNT_FILE が未設定です（Drive直読みON）", file=sys.stderr); sys.exit(2)

    # 環境変数を下位スクリプトに引き継ぐ
    os.environ["NOTION_TOKEN"] = NOTION_TOKEN
    os.environ["NOTION_DB_ID"] = NOTION_DB_ID
    os.environ["CSV_PATH"] = CSV_PATH
    os.environ["LOG_DIR"] = LOG_DIR
    if SERVICE_ACCOUNT_FILE:
        os.environ["SERVICE_ACCOUNT_FILE"] = SERVICE_ACCOUNT_FILE
    if READ_FROM_DRIVE:
        os.environ["READ_FROM_DRIVE"] = "1"
        if DRIVE_ROOT_ID:
            os.environ["DRIVE_ROOT_ID"] = DRIVE_ROOT_ID
    if DRY_RUN:
        os.environ["DRY_RUN"] = "1"
    else:
        os.environ.pop("DRY_RUN", None)

    # === [1/2] AppendCSV ===
    print("=== [1/2] AppendCSV_New ===")
    run(["python3", "run_all_append_csv_new_save.py"])

    # === [2/2] Notion Upsert ===
    print("=== [2/2] Notion Upsert ===")
    run(["python3", "notion_upsert_from_csv_save.py"])

    print("✅ DONE")

if __name__ == "__main__":
    main()
