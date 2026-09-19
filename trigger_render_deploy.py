"""Trigger Render deploy for CFBAllenRatings and poll until live."""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import requests

CLI_YAML = Path.home() / ".render" / "cli.yaml"
SITE_URL = "https://cfballenratings.onrender.com/"


def api_key() -> str:
    text = CLI_YAML.read_text(encoding="utf-8")
    match = re.search(r"key:\s+(rnd_\S+)", text)
    if not match:
        raise SystemExit(f"No API key in {CLI_YAML}")
    return match.group(1)


def headers(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}", "Accept": "application/json"}


def find_service(key: str) -> tuple[str, str]:
    resp = requests.get(
        "https://api.render.com/v1/services",
        params={"limit": 50},
        headers=headers(key),
        timeout=60,
    )
    resp.raise_for_status()
    for item in resp.json():
        svc = item["service"]
        name = svc.get("name", "")
        url = (svc.get("serviceDetails") or {}).get("url", "")
        repo = (svc.get("repo") or "")
        if name == "CFBAllenRatings" or "cfballenratings" in (url or ""):
            return svc["id"], name
        if "cfb-allen-ratings" in repo:
            return svc["id"], name
    raise SystemExit("CFBAllenRatings service not found on Render")


def trigger_deploy(key: str, service_id: str) -> str:
    resp = requests.post(
        f"https://api.render.com/v1/services/{service_id}/deploys",
        headers={**headers(key), "Content-Type": "application/json"},
        json={"clearCache": "clear"},
        timeout=60,
    )
    resp.raise_for_status()
    deploy = resp.json()
    return deploy["id"]


def wait_deploy(key: str, service_id: str, deploy_id: str, timeout_s: int = 900) -> str:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        resp = requests.get(
            f"https://api.render.com/v1/services/{service_id}/deploys/{deploy_id}",
            headers=headers(key),
            timeout=60,
        )
        resp.raise_for_status()
        status = resp.json().get("status", "unknown")
        print(f"deploy_status={status}")
        if status == "live":
            return status
        if status in {"build_failed", "update_failed", "canceled", "deactivated"}:
            raise SystemExit(f"Deploy failed with status: {status}")
        time.sleep(20)
    raise SystemExit("Deploy timed out")


def site_has_overall() -> bool:
    resp = requests.get(SITE_URL, timeout=120)
    resp.raise_for_status()
    html = resp.text
    has_overall = "Overall" in html and 'value="overall"' in html
    has_blended_col = ">Blended<" in html or "data-sort=\"num\">Blended" in html
    print(f"site_overall={has_overall} site_blended_col={has_blended_col}")
    return has_overall and not has_blended_col


def main() -> None:
    key = api_key()
    service_id, name = find_service(key)
    print(f"service_id={service_id} name={name}")
    deploy_id = trigger_deploy(key, service_id)
    print(f"deploy_id={deploy_id}")
    final = wait_deploy(key, service_id, deploy_id)
    print(f"final_status={final}")
    if not site_has_overall():
        raise SystemExit("Deploy live but site still shows old UI")
    print("SUCCESS")


if __name__ == "__main__":
    main()
