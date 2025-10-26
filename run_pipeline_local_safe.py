#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, subprocess, sys

# === 設定値を環境変数から取得 ===
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
NOTION_DB_ID = os.environ.get("NOTION_DB_ID")

# ▼▼▼ ここだけ修正（CSVはリポ直下の既定に統一） ▼▼▼
CSV_PATH = os.environ.get("CSV_PATH", "ChatGPT_Merge_master.csv")
# ▲▲▲ 修正はこの1行のみ ▲▲▲

CDIR = os.getcwd()

# DRY_RUNフラグ：環境変数または手動で制御
DRY_RUN = os.environ.get("DRY_RUN", "False").lower() in ("1", "true")

# === 以下、自動実行部分 ===
def run(cmd):
    print(">>>", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)

def main():
    # ローカル実行時は、もし環境変数が空なら警告を出す
    if not NOTION_TOKEN or not NOTION_DB_ID:
        print("⚠️ NOTION_TOKEN または NOTION_DB_ID が設定されていません。")
        print("GitHub Secrets または環境変数を確認してください。")
        sys.exit(1)

    # 参照パス表示（既存の出力フォーマットそのまま）
    print(f"📂 現在の作業ディレクトリ: {CDIR}")
    print(f"🗂 参照CSV: {CSV_PATH}")
    print(f"🗒 ログ出力先: {os.path.join(CDIR, 'logs')}")

    # 環境変数を一時的に渡す
    os.environ["NOTION_TOKEN"] = NOTION_TOKEN
    os.environ["NOTION_DB_ID"] = NOTION_DB_ID
    os.environ["CSV_PATH"] = CSV_PATH
    if DRY_RUN:
        os.environ["DRY_RUN"] = "1"
    else:
        os.environ.pop("DRY_RUN", None)

    # スクリプト実行
    print("=== [1/2] AppendCSV_New ===")
    run(["python3", "run_all_append_csv_new_save.py"])

    print("=== [2/2] Notion Upsert ===")
    run(["python3", "notion_upsert_from_csv_save.py"])

    print("✅ DONE")

if __name__ == "__main__":
    main()
