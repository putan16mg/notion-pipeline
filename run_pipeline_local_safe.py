#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, subprocess, sys

# === 設定値を環境変数から取得（ローカル/CI 両対応） ===
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
NOTION_DB_ID = os.environ.get("NOTION_DB_ID")

# ローカル既定値（あなたの固定パスはそのまま残す）
CSV_PATH_LOCAL = "/Users/odaakihisa/Documents/Notion_Auto/automation/data/ChatGPT_Merge_master.csv"
CDIR_LOCAL     = "/Users/odaakihisa/Documents/Notion_Auto/automation"

# CI（GitHub Actions）では自動で作業ディレクトリに切替
IS_CI = os.environ.get("GITHUB_ACTIONS", "").lower() == "true"
if IS_CI:
    # GitHub Actions の作業ディレクトリ（例: /home/runner/work/<repo>/<repo>）
    CDIR = os.getcwd()
    # CSV_PATH は Secrets/環境で渡されていなければ、リポ内 data/ を既定に
    CSV_PATH = os.environ.get("CSV_PATH", os.path.join(CDIR, "data/ChatGPT_Merge_master.csv"))
else:
    CDIR = CDIR_LOCAL
    CSV_PATH = os.environ.get("CSV_PATH", CSV_PATH_LOCAL)

# DRY_RUNフラグ：環境変数または手動で制御（既定 False）
DRY_RUN = os.environ.get("DRY_RUN", "False").lower() in ("1", "true", "yes")

# === 実行関数（そのまま） ===
def run(cmd):
    print(">>>", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)

def main():
    # トークン必須チェック（そのまま）
    if not NOTION_TOKEN or not NOTION_DB_ID:
        print("⚠️ NOTION_TOKEN または NOTION_DB_ID が設定されていません。")
        print("GitHub Secrets または環境変数を確認してください。")
        sys.exit(1)

    # スクリプトに渡す環境変数をここで統一セット（そのまま）
    os.environ["NOTION_TOKEN"] = NOTION_TOKEN
    os.environ["NOTION_DB_ID"] = NOTION_DB_ID
    os.environ["CSV_PATH"] = CSV_PATH
    if DRY_RUN:
        os.environ["DRY_RUN"] = "1"
    else:
        os.environ.pop("DRY_RUN", None)

    # 作業ディレクトリへ移動（ローカル/CIで分岐済み）
    os.chdir(CDIR)
    print(f"📂 現在の作業ディレクトリ: {CDIR}")
    print(f"🗂 参照CSV: {os.environ.get('CSV_PATH')}")

    # === [1/2] CSV追記（名前だけ _save に変更） ===
    print("=== [1/2] AppendCSV_New ===")
    run(["python3", "run_all_append_csv_new_save.py"])

    # === [2/2] Notion反映（名前だけ _save に変更） ===
    print("=== [2/2] Notion Upsert ===")
    run(["python3", "notion_upsert_from_csv_save.py"])

    print("✅ DONE")

if __name__ == "__main__":
    main()
