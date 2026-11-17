# -*- coding: utf-8 -*-
"""Images gratuites via Pollinations (aucune cle), renvoyees en data URL."""
import base64
import time
import urllib.parse
import urllib.request


def _est_image_valide(data):
    return data[:2] == b"\xff\xd8" or data[:8] == b"\x89PNG\r\n\x1a\n"


def generer_data_url(prompt, seed=None, taille=1024, timeout=180):
    params = {"width": taille, "height": taille, "nologo": "true"}
    if seed is not None:
        params["seed"] = int(seed)
    url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt)
    url += "&" + urllib.parse.urlencode(params)

    derniere = None
    for tentative in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
            if len(data) >= 1000 and _est_image_valide(data):
                mime = "image/jpeg" if data[:2] == b"\xff\xd8" else "image/png"
                b64 = base64.b64encode(data).decode("ascii")
                return f"data:{mime};base64,{b64}"
            derniere = RuntimeError("reponse non image (service sature)")
        except Exception as e:
            derniere = e
        time.sleep(2 + tentative * 2)
    raise RuntimeError(f"generation d'image impossible : {derniere}")
