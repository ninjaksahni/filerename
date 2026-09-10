from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

STORE_PATH = Path(__file__).resolve().parent / "sku_mappings.json"

GST_CODES = {
    "01": "JK",
    "02": "HP",
    "03": "PB",
    "04": "CH",
    "05": "UK",
    "06": "HR",
    "07": "DL",
    "08": "RJ",
    "09": "UP",
    "10": "BR",
    "11": "SK",
    "12": "AR",
    "13": "NL",
    "14": "MN",
    "15": "MZ",
    "16": "TR",
    "17": "ML",
    "18": "AS",
    "19": "WB",
    "20": "JH",
    "21": "OD",
    "22": "CG",
    "23": "MP",
    "24": "GJ",
    "25": "DD",
    "26": "DN",
    "27": "MH",
    "28": "AP",
    "29": "KA",
    "30": "GA",
    "31": "LD",
    "32": "KL",
    "33": "TN",
    "34": "PY",
    "35": "AN",
    "36": "TS",
    "37": "AP",
    "38": "LA",
}

STATE_ABBREVIATIONS = {
    "Andaman and Nicobar Islands": "AN",
    "Andaman & Nicobar": "AN",
    "Andaman and Nicobar": "AN",
    "Andhra Pradesh": "AP",
    "Andhra": "AP",
    "Arunachal Pradesh": "AR",
    "Assam": "AS",
    "Bihar": "BR",
    "Chandigarh": "CH",
    "Chhattisgarh": "CG",
    "Chattisgarh": "CG",
    "Dadra and Nagar Haveli and Daman and Diu": "DN",
    "Dadra and Nagar Haveli": "DN",
    "Daman and Diu": "DD",
    "Delhi": "DL",
    "NCT of Delhi": "DL",
    "New Delhi": "DL",
    "Goa": "GA",
    "Gujarat": "GJ",
    "Haryana": "HR",
    "Himachal Pradesh": "HP",
    "Jammu and Kashmir": "JK",
    "Jammu & Kashmir": "JK",
    "Jharkhand": "JH",
    "Karnataka": "KA",
    "Kerala": "KL",
    "Ladakh": "LA",
    "Lakshadweep": "LD",
    "Madhya Pradesh": "MP",
    "Maharashtra": "MH",
    "Maharastra": "MH",
    "Maharastha": "MH",
    "Mahrashtra": "MH",
    "Maharasthra": "MH",
    "Manipur": "MN",
    "Meghalaya": "ML",
    "Mizoram": "MZ",
    "Nagaland": "NL",
    "Odisha": "OD",
    "Orissa": "OD",
    "Puducherry": "PY",
    "Pondicherry": "PY",
    "Punjab": "PB",
    "Rajasthan": "RJ",
    "Sikkim": "SK",
    "Tamil Nadu": "TN",
    "TamilNadu": "TN",
    "Tamilnadu": "TN",
    "Telangana": "TS",
    "Telengana": "TS",
    "Tripura": "TR",
    "Uttar Pradesh": "UP",
    "UttarPradesh": "UP",
    "Uttarakhand": "UK",
    "Uttrakhand": "UK",
    "Uttaranchal": "UK",
    "West Bengal": "WB",
    "WestBengal": "WB",
}

def _normalize_name(value: str) -> str:
    text = value.strip().lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def default_store() -> dict[str, Any]:
    return {
        "sku_mappings": {},
        "gst_codes": dict(GST_CODES),
        "state_abbreviations": dict(STATE_ABBREVIATIONS),
    }


def load_store(path: Path | None = None) -> dict[str, Any]:
    store_path = path or STORE_PATH
    data = default_store()
    if store_path.exists():
        loaded = json.loads(store_path.read_text(encoding="utf-8"))
        if isinstance(loaded.get("sku_mappings"), dict):
            data["sku_mappings"] = {
                str(key): str(value) for key, value in loaded["sku_mappings"].items()
            }
        if isinstance(loaded.get("gst_codes"), dict):
            data["gst_codes"] = {
                str(key): str(value).upper() for key, value in loaded["gst_codes"].items()
            }
        if isinstance(loaded.get("state_abbreviations"), dict):
            data["state_abbreviations"] = {
                str(key): str(value).upper()
                for key, value in loaded["state_abbreviations"].items()
            }
    else:
        save_store(data, store_path)
    return data


def save_store(data: dict[str, Any], path: Path | None = None) -> None:
    store_path = path or STORE_PATH
    store_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def save_sku_mappings(
    sku_mappings: dict[str, str], path: Path | None = None
) -> dict[str, Any]:
    data = load_store(path)
    data["sku_mappings"] = dict(sku_mappings)
    save_store(data, path)
    return data


def lookup_place_code(
    state_name: str | None,
    gst_code: str | None,
    data: dict[str, Any] | None = None,
) -> str | None:
    store = data or load_store()
    if gst_code:
        padded = gst_code.strip().zfill(2)
        code = store["gst_codes"].get(padded) or store["gst_codes"].get(gst_code.strip())
        if code:
            return str(code).upper()

    if not state_name:
        return None

    abbreviations: dict[str, str] = store["state_abbreviations"]
    if state_name in abbreviations:
        return abbreviations[state_name].upper()

    wanted = _normalize_name(state_name)
    for name, code in abbreviations.items():
        if _normalize_name(name) == wanted:
            return str(code).upper()
    return None
