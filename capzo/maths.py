# -*- coding: utf-8 -*-
"""Moteur de calcul exact (sympy) pour Capzo IA.

But : savoir resoudre des equations, derivees, integrales, systemes, matrices...
et renvoyer un resultat **exact** (pas une approximation racontee par un LLM).

Utilisation :
    maths.traiter("resous 2x^2 - 5x + 3 = 0")  -> dict ou None
    maths.contexte(message)                     -> texte a injecter dans le prompt
"""
import re

MOTS_CALCUL = (
    "calcule", "calculer", "combien font", "combien fait", "combien vaut",
    "résous", "resous", "résoudre", "resoudre", "résolution", "resolution",
    "équation", "equation", "système", "systeme", "dérivée", "derivee",
    "dériver", "deriver", "intégrale", "integrale", "intégrer", "integrer",
    "primitive", "limite", "simplifie", "simplifier", "factorise", "factoriser",
    "développe", "developpe", "développer", "determinant", "déterminant",
)

VARIABLES = "xyzabcdefghijklmnopqrstuvw"


def _sympy():
    try:
        import sympy
        return sympy
    except Exception:
        return None


def _normaliser(texte):
    t = (texte or "").strip()
    t = t.replace("×", "*").replace("÷", "/").replace("−", "-").replace("–", "-")
    t = t.replace("^", "**").replace("π", "pi").replace("²", "**2").replace("³", "**3")
    t = re.sub(r"\bracine (?:carr[ée]e )?de\b", "sqrt", t)
    t = re.sub(r"\b(?:au carr[ée]|carr[ée])\b", "**2", t)
    t = re.sub(r"\b(?:au cube)\b", "**3", t)
    # multiplication implicite : 2x, 3(x+1), 2xy, )(, )x
    t = re.sub(r"(\d)\s*([a-zA-Z(])", r"\1*\2", t)
    t = re.sub(r"\)\s*(\()", r")*\1", t)
    t = re.sub(r"\)\s*([a-zA-Z0-9])", r")*\1", t)
    t = re.sub(r"([a-zA-Z])\s*(\()", r"\1*\2", t)
    # 2 x -> 2*x deja gere ; espaces autour des operateurs
    t = re.sub(r"\s*([+\-*/=,;])\s*", r"\1", t)
    return t


def _symboles(sympy, texte):
    lettres = sorted({c for c in texte if c in VARIABLES})
    return {c: sympy.Symbol(c) for c in lettres}


def _fmt(sympy, valeur):
    try:
        if isinstance(valeur, (list, tuple, set)):
            return ", ".join(_fmt(sympy, v) for v in valeur)
        v = sympy.simplify(valeur)
        if v.is_Integer:
            return str(int(v))
        if v.is_Float:
            return str(round(float(v), 10))
        return str(v)
    except Exception:
        return str(valeur)


def _extraire(message):
    """Devine l'operation demandee. Retourne (op, expression, variable) ou None."""
    bas = (message or "").lower().strip()
    if not bas or len(bas) > 260:
        return None
    variable = "x"
    m = re.search(r"(?:par rapport [àa]|en fonction de|d'?inconnue)\s+([a-z])\b", bas)
    if m:
        variable = m.group(1)

    # derivee
    m = re.search(r"(?:d[ée]riv[ée]e?|d[ée]river)\s+(?:de\s+|la fonction\s+)?(.+)$", bas)
    if m:
        return ("derivee", m.group(1), variable)
    # integrale
    m = re.search(r"(?:int[ée]grale?|primitive)\s+(?:de\s+)?(.+)$", bas)
    if m:
        return ("integrale", m.group(1), variable)
    # limite
    m = re.search(r"limite\s+(?:de\s+)?(.+?)(?:\s+quand\s+|\s+en\s+)([a-z])\s*(?:->|→|tend vers)\s*([^\s,]+)$", bas)
    if m:
        return ("limite", m.group(1) + "|" + m.group(2) + "|" + m.group(3), variable)
    # factoriser / developper / simplifier
    for op, motif in (("factoriser", r"factoris\w*\s+(.+)"),
                      ("developper", r"d[ée]velopp\w*\s+(.+)" ),
                      ("simplifier", r"simplifi\w*\s+(.+)"),
                      ("determinant", r"d[ée]terminant\s+(?:de\s+)?(.+)")):
        m = re.search(motif, bas)
        if m:
            return (op, m.group(1), variable)
    # systeme (plusieurs equations)
    if bas.count("=") >= 2:
        return ("systeme", bas, variable)
    # equation simple
    if "=" in bas:
        return ("equation", bas, variable)
    # calcul arithmetique / algebrique
    if re.search(r"\d", bas) and re.search(r"[+\-*/^()]", bas):
        return ("calcul", bas, variable)
    return None


def _nettoyer_expression(expr):
    e = _normaliser(expr)
    e = re.sub(r"[?]+$", "", e).strip()
    e = re.sub(r"\s*(?:svp|s'il te plait|stp|merci)\s*$", "", e)
    verbes = ("combien font", "combien fait", "combien vaut", "calculez", "calculer",
              "calcule", "résoudre", "resoudre", "résous", "resous", "resolution",
              "résolution", "resolution", "equation", "équation", "systeme", "système",
              "trouve", "trouver", "donne", "donner", "det", "peux tu", "peux-tu",
              "de", "la", "le", "les", "l'", "un", "une")
    change = True
    while change:
        change = False
        e = e.strip()
        for v in verbes:
            if e.lower().startswith(v):
                e = e[len(v):].strip()
                change = True
    return e.strip()


def _pourcentage(bas):
    m = re.search(r"(-?\d+(?:[.,]\d+)?)\s*%\s*(?:de|du|des|sur)\s*(-?\d+(?:[.,]\d+)?)", bas)
    if not m:
        return None
    a = float(m.group(1).replace(",", "."))
    b = float(m.group(2).replace(",", "."))
    valeur = a * b / 100.0
    if abs(valeur - round(valeur)) < 1e-12:
        texte = str(int(round(valeur)))
    else:
        texte = f"{valeur:.10g}"
    return {"operation": "pourcentage",
            "resultat": texte,
            "details": f"{a:g}% de {b:g} = {a:g}/100 × {b:g}"}


def traiter(message):
    """Renvoie {"operation", "resultat", "details"} ou None si ce n'est pas un calcul."""
    sympy = _sympy()
    if sympy is None:
        return None
    pct = _pourcentage((message or "").lower())
    if pct:
        return pct
    demande = _extraire(message)
    if not demande:
        return None
    op, brut, variable = demande
    data = _nettoyer_expression(brut)
    if op not in ("systeme", "determinant"):
        data = re.sub(r"(\d),(\d)", r"\1.\2", data)
    if not data or len(data) > 200:
        return None

    try:
        if op == "limite":
            expr, var, vers = data.split("|")
            expr = _nettoyer_expression(expr)
            vers = _nettoyer_expression(vers)
            v = sympy.Symbol(var)
            point = sympy.oo if vers.lower() in ("infini", "+infini", "inf", "+inf") else (
                -sympy.oo if vers.lower() in ("-infini", "-inf") else sympy.sympify(vers))
            res = sympy.limit(sympy.sympify(expr, locals={var: v}), v, point)
            return {"operation": "limite",
                    "resultat": _fmt(sympy, res),
                    "details": f"limite de {expr} quand {var} → {vers}"}

        if op == "derivee":
            v = sympy.Symbol(variable)
            expr = sympy.sympify(data, locals={variable: v})
            res = sympy.diff(expr, v)
            simplified = sympy.simplify(res)
            return {"operation": "derivee",
                    "resultat": _fmt(sympy, simplified),
                    "details": f"d/d{variable} ( {expr} ) = {simplified}"}

        if op == "integrale":
            v = sympy.Symbol(variable)
            expr = sympy.sympify(data, locals={variable: v})
            res = sympy.integrate(expr, v)
            return {"operation": "integrale",
                    "resultat": _fmt(sympy, res) + " + C",
                    "details": f"∫ {expr} d{variable} = {res} + C"}

        if op == "factoriser":
            expr = sympy.sympify(data)
            return {"operation": "factoriser", "resultat": _fmt(sympy, sympy.factor(expr)),
                    "details": f"factorisation de {expr}"}

        if op == "developper":
            expr = sympy.sympify(data)
            return {"operation": "developper", "resultat": _fmt(sympy, sympy.expand(expr)),
                    "details": f"developpement de {expr}"}

        if op == "simplifier":
            expr = sympy.sympify(data)
            return {"operation": "simplifier", "resultat": _fmt(sympy, sympy.simplify(expr)),
                    "details": f"simplification de {expr}"}

        if op == "determinant":
            lignes = re.findall(r"\[([^\[\]]+)\]", data)
            if len(lignes) < 2:
                nombres = re.findall(r"-?\d+(?:[.,]\d+)?(?:/\d+)?", data)
                if len(nombres) == 4:
                    lignes = [nombres[0] + "," + nombres[1], nombres[2] + "," + nombres[3]]
                elif len(nombres) == 9:
                    lignes = [",".join(nombres[i:i + 3]) for i in (0, 3, 6)]
            if len(lignes) >= 2:
                M = sympy.Matrix([[sympy.sympify(x) for x in ligne.split(",") if x.strip()]
                                  for ligne in lignes])
                return {"operation": "determinant", "resultat": _fmt(sympy, M.det()),
                        "details": "determinant de " + str(M.tolist())}
            return None

        if op == "systeme":
            equations = [e for e in re.split(r"[;,]", data) if "=" in e]
            eqs, variables = [], []
            for brut_eq in equations:
                gauche, droite = brut_eq.split("=", 1)
                g = sympy.sympify(gauche)
                d = sympy.sympify(droite)
                eqs.append(sympy.Eq(g, d))
                for s in (g.free_symbols | d.free_symbols):
                    if s not in variables:
                        variables.append(s)
            variables = sorted(variables, key=lambda s: s.name)
            res = sympy.solve(eqs, variables, dict=True)
            if not res:
                return None
            texte = " ; ".join(", ".join(f"{k} = {_fmt(sympy, v)}" for k, v in solution.items())
                                for solution in res)
            return {"operation": "systeme", "resultat": texte,
                    "details": "resolution du systeme " + " ; ".join(str(e) for e in eqs)}

        if op == "equation":
            gauche, droite = data.split("=", 1)
            g = sympy.sympify(gauche)
            d = sympy.sympify(droite)
            inconnues = sorted(g.free_symbols | d.free_symbols, key=lambda s: s.name)
            if not inconnues:
                return {"operation": "egalite", "details": f"{g} = {d}",
                        "resultat": "vrai" if sympy.simplify(g - d) == 0 else "faux"}
            res = sympy.solve(sympy.Eq(g, d), inconnues[0], dict=False)
            if not res:
                return None
            if not isinstance(res, (list, tuple)):
                res = [res]
            return {"operation": "equation",
                    "resultat": f"{inconnues[0]} = " + " ou ".join(_fmt(sympy, r) for r in res),
                    "details": f"resolution exacte de {g} = {d}"}

        # calcul
        expr = sympy.sympify(data)
        exact = sympy.simplify(expr)
        texte = _fmt(sympy, exact)
        try:
            approche = float(exact)
            if abs(approche) > 1e15 or abs(approche) < 1e-6:
                texte += f"  (≈ {approche:.6g})"
            elif exact != int(approche) if getattr(exact, "is_Integer", False) is False else False:
                texte += f"  (≈ {approche:.10g})"
        except Exception:
            pass
        return {"operation": "calcul", "resultat": texte, "details": f"calcul de {expr}"}
    except Exception:
        return None


def contexte(message):
    """Phrase a injecter dans le prompt systeme, ou chaine vide."""
    r = traiter(message)
    if not r:
        return ""
    return ("\n\n=== CALCUL EXACT (sympy, fiable) ===\n"
            "Le resultat ci-dessous est calcule par un moteur mathematique exact : "
            "donne-le TEL QUEL, sans le recalculer.\n"
            + r.get("details", "") + "\nResultat exact : " + r["resultat"] +
            "\nExplique ensuite la demarche en francais, simplement.")
