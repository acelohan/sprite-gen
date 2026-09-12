#!/usr/bin/env python3
"""
Adapter: Generate sprite via apithat gpt-image-2 with native RGBA transparency.
"""
import base64
import json
import os
import subprocess
import sys
import urllib.request
import numpy as np
from PIL import Image

def get_api_key():
    return subprocess.check_output([
        "infisical-run", "secrets", "get", "APITHAT_IMAGE",
        "--env=prod", "--path=/custom-provider", "--plain"
    ], text=True).strip()

def generate_sprite(prompt: str, out_path: str, model: str = "gpt-image-2"):
    api_key = get_api_key()
    url = "https://apithat.dev/v1/images/generations"
    payload = {
        "model": model,
        "prompt": prompt,
        "size": "1024x1024",
        "n": 1,
        "response_format": "b64_json"
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }
    )
    print(f"[1/2] Generating image via {model}...")
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    
    b64_data = data["data"][0].get("b64_json")
    if not b64_data and "url" in data["data"][0]:
        img_url = data["data"][0]["url"]
        img_req = urllib.request.Request(img_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(img_req) as img_resp:
            raw_bytes = img_resp.read()
    else:
        raw_bytes = base64.b64decode(b64_data)

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    raw_path = out_path + ".raw.png"
    with open(raw_path, "wb") as f:
        f.write(raw_bytes)

    # Process native transparency
    print(f"[2/2] Validating and cleaning native alpha channel...")
    img = Image.open(raw_path)
    if img.mode != "RGBA":
        print(f"Warning: Image mode is {img.mode}, running cutout fallback...")
        cmd = ["/home/hermes-agent/sprite-gen/.venv/bin/sprite-gen", "cutout", raw_path, "--out", out_path]
        subprocess.check_call(cmd)
        return

    arr = np.array(img)
    # Scrub dirty RGB under zero/near-zero alpha (< 5)
    mask = arr[:, :, 3] < 5
    arr[mask, 3] = 0
    arr[mask, :3] = 0

    clean_img = Image.fromarray(arr)
    clean_img.save(out_path)

    alpha_hist = clean_img.getchannel("A").histogram()
    trans_pct = alpha_hist[0] / (clean_img.size[0] * clean_img.size[1]) * 100
    print(f"Done! Clean transparent RGBA ({trans_pct:.1f}% alpha 0) -> {out_path}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python generate_and_cutout.py <output_path> <prompt>")
        sys.exit(1)
    out_file = sys.argv[1]
    prompt_text = sys.argv[2]
    generate_sprite(prompt_text, out_file)
