# -*- coding: utf-8 -*-
"""Animations 2D : SVG anime. Tente une creation par l'IA, sinon rendu procedural."""
import html
import random
import re

from . import llm

CONSIGNE_SVG = (
    "Reponds UNIQUEMENT avec un code SVG complet et soigne "
    '(attribut viewBox="0 0 512 512", sans script, sans foreignObject, sans texte autour). '
    "L'animation doit etre fluide, en boucle infinie d'environ 6 secondes, realisee avec "
    "<animate>, <animateTransform> ou <animateMotion>. Utilise des couleurs sombres et "
    "cinematographiques. Scene : "
)


def _extraire_svg(texte):
    if not texte:
        return None
    m = re.search(r"<svg[\s\S]*?</svg>", texte, re.IGNORECASE)
    if not m:
        return None
    svg = m.group(0)
    svg = re.sub(r"<script[\s\S]*?</script>", "", svg, flags=re.IGNORECASE)
    svg = re.sub(r"<foreignObject[\s\S]*?</foreignObject>", "", svg, flags=re.IGNORECASE)
    svg = re.sub(r"\son\w+\s*=\s*(\"[^\"]*\"|'[^']*')", "", svg, flags=re.IGNORECASE)
    if "animate" not in svg.lower() or len(svg) > 40000:
        return None
    return svg


def svg_depuis_ia(prompt):
    try:
        brut = llm.complete(CONSIGNE_SVG + str(prompt)[:500], system=None)
        return _extraire_svg(brut)
    except Exception:
        return None


def svg_procedural(prompt):
    """Ambiance animee sombre : ciel, etoiles, brume, halo pulsant, titre."""
    rnd = random.Random(abs(hash(str(prompt))) % 100000)
    titre = " ".join(str(prompt).split()[:4]).upper()[:28] or "CAPZO"
    titre = html.escape(titre)

    etoiles = []
    for _ in range(46):
        cx = rnd.randint(8, 504)
        cy = rnd.randint(8, 330)
        r = round(rnd.uniform(0.6, 1.8), 2)
        d = round(rnd.uniform(2.2, 5.5), 2)
        retard = round(rnd.uniform(0, 3), 2)
        etoiles.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#d7e6ff">'
            f'<animate attributeName="opacity" values="0.15;0.95;0.15" '
            f'dur="{d}s" begin="{retard}s" repeatCount="indefinite"/></circle>'
        )

    brumes = []
    for i in range(3):
        cy = 300 + i * 70
        rx = 150 + i * 40
        op = 0.10 - i * 0.02
        dur = 11 + i * 3
        brumes.append(
            f'<ellipse cx="256" cy="{cy}" rx="{rx}" ry="52" fill="#8fb3d6" opacity="{op:.2f}" '
            f'filter="url(#flou)">'
            f'<animateTransform attributeName="transform" type="translate" '
            f'values="0 0; {40 + i * 25} -12; 0 0" dur="{dur}s" repeatCount="indefinite"/>'
            f"</ellipse>"
        )

    return f"""<svg viewBox="0 0 512 512" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="ciel" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#0b1624"/>
      <stop offset="60%" stop-color="#0a1018"/>
      <stop offset="100%" stop-color="#05070a"/>
    </linearGradient>
    <radialGradient id="halo" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#9fc6ef" stop-opacity="0.55"/>
      <stop offset="60%" stop-color="#4f7aa8" stop-opacity="0.18"/>
      <stop offset="100%" stop-color="#000000" stop-opacity="0"/>
    </radialGradient>
    <filter id="flou"><feGaussianBlur stdDeviation="14"/></filter>
  </defs>
  <rect width="512" height="512" fill="url(#ciel)"/>
  <g>{"".join(etoiles)}</g>
  <circle cx="256" cy="236" r="128" fill="url(#halo)">
    <animate attributeName="r" values="112;138;112" dur="5.5s" repeatCount="indefinite"/>
    <animate attributeName="opacity" values="0.75;1;0.75" dur="5.5s" repeatCount="indefinite"/>
  </circle>
  <g>{"".join(brumes)}</g>
  <text x="256" y="468" text-anchor="middle" font-family="Georgia, 'Times New Roman', serif"
        font-size="30" fill="#eaf1f8" opacity="0">
    {titre}
    <animate attributeName="opacity" values="0;0.9;0.9;0" dur="8s"
             keyTimes="0;0.15;0.75;1" repeatCount="indefinite"/>
  </text>
</svg>"""


def fabriquer(prompt, narration=""):
    """Renvoie un SVG anime procedural (instantane, aucune dependance reseau)."""
    return {"svg": svg_procedural(prompt or narration or "une ambiance sombre"),
            "narration": narration}
