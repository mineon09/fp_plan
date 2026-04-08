"""
Module 1: 銀行金利データ取得
- AIプロンプト自動生成
- JSON貼り付けパース・バリデーション
"""

import json
import re
from datetime import datetime
from typing import Any

from config import DEFAULT_BANKS, RATE_MIN, RATE_MAX


REQUIRED_FIELDS = {"bank_name", "variable_35", "fixed_35"}
OPTIONAL_FIELDS = {"fixed_10", "fixed_5", "fixed_3", "has_team_dan", "notes"}

_PROMPT_TEMPLATE = """\
以下の銀行の住宅ローン金利（{year}年{month}月現在の適用金利）を
厳密にJSON形式のみで返答してください。前置き・説明文は不要です。

対象銀行: {bank_list}

出力フォーマット:
{{
  "fetch_date": "YYYY-MM",
  "banks": [
    {{
      "bank_name": "銀行名",
      "variable_35": 数値,
      "fixed_35": 数値,
      "fixed_10": 数値,
      "has_team_dan": true,
      "notes": "備考"
    }}
  ]
}}

注意事項:
- 変動金利がない場合は null を使用してください
- 金利は % 単位の数値（例: 0.32）で返してください
- 現在取り扱いがない場合も null ではなく最新の参考値を入れてください
"""


def generate_prompt(bank_names: list[str]) -> str:
    now = datetime.now()
    return _PROMPT_TEMPLATE.format(
        year=now.year,
        month=now.month,
        bank_list="、".join(bank_names),
    )


def parse_and_validate(raw_text: str) -> dict[str, Any]:
    """
    AIが返したテキストをパースし検証する。
    Returns:
        {
            "ok": bool,
            "banks": list[dict],      # バリデーション済み銀行リスト
            "errors": list[str],      # エラーメッセージ
            "warnings": list[str],    # 警告メッセージ
            "fetch_date": str,
        }
    """
    result = {"ok": False, "banks": [], "errors": [], "warnings": [], "fetch_date": ""}

    # JSON 部分だけ抽出（前後の説明文を除去）
    json_match = re.search(r"\{[\s\S]*\}", raw_text)
    if not json_match:
        result["errors"].append("JSONが見つかりません。AI出力をそのまま貼り付けてください。")
        return result

    try:
        data = json.loads(json_match.group())
    except json.JSONDecodeError as e:
        result["errors"].append(f"JSONパースエラー: {e}")
        return result

    if "banks" not in data or not isinstance(data["banks"], list):
        result["errors"].append('"banks" 配列が見つかりません。')
        return result

    # fetch_date 処理
    fetch_date = data.get("fetch_date", "")
    if not re.match(r"^\d{4}-\d{2}$", str(fetch_date)):
        fetch_date = datetime.now().strftime("%Y-%m")
        result["warnings"].append(f"fetch_date が不正なため当月 ({fetch_date}) で補完しました。")
    result["fetch_date"] = fetch_date

    # 銀行名重複排除（後者優先）
    seen: dict[str, dict] = {}
    for bank in data["banks"]:
        name = bank.get("bank_name", "")
        if name in seen:
            result["warnings"].append(f"銀行名「{name}」が重複しています。後者の値を使用します。")
        seen[name] = bank

    validated_banks = []
    for name, bank in seen.items():
        bank_result = dict(bank)

        # 必須フィールドチェック
        missing = REQUIRED_FIELDS - set(bank.keys())
        if missing:
            result["errors"].append(f"「{name}」に必須フィールドが不足: {missing}")
            continue

        # 金利範囲チェック
        for field in ("variable_35", "fixed_35", "fixed_10", "fixed_5", "fixed_3"):
            val = bank.get(field)
            if val is not None:
                try:
                    val = float(val)
                    bank_result[field] = val
                    if not (RATE_MIN <= val <= RATE_MAX):
                        result["warnings"].append(
                            f"「{name}」の {field}={val}% は範囲外 ({RATE_MIN}%〜{RATE_MAX}%) です。"
                        )
                except (TypeError, ValueError):
                    result["errors"].append(f"「{name}」の {field} が数値ではありません: {val}")

        validated_banks.append(bank_result)

    result["banks"] = validated_banks
    result["ok"] = len(result["errors"]) == 0 and len(validated_banks) > 0
    return result


def get_default_banks() -> list[dict]:
    return [dict(b) for b in DEFAULT_BANKS]
