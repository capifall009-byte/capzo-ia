# -*- coding: utf-8 -*-
"""Generateur de quiz deterministe : instantane, gratuit, sans cle API.

Utilise quand le moteur local est trop limite pour produire un quiz fiable.
Avec une cle Groq, le LLM peut aussi en generer sur n'importe quel sujet.
"""
import random
import re
import unicodedata


def _norm(texte):
    """Ignore les accents : « planètes » doit trouver « planete »."""
    return "".join(c for c in unicodedata.normalize("NFD", (texte or "").lower())
                   if not unicodedata.combining(c))

# Chaque question : (categorie, question, bonne reponse, [propositions], explication)
BANQUE = [
    # ---------------------------------------------------------------- Sciences
    ("sciences", "Quelle est la formule chimique de l'eau ?", "H2O",
     ["H2O", "CO2", "O2", "NaCl"], "Deux atomes d'hydrogene et un d'oxygene."),
    ("sciences", "Combien de planetes composent le systeme solaire ?", "8",
     ["8", "9", "7", "10"], "Pluton a ete declasse en 2006 : il reste huit planetes."),
    ("sciences", "Quelle particule porte une charge negative ?", "Electron",
     ["Electron", "Proton", "Neutron", "Photon"], "Le proton est positif, le neutron neutre."),
    ("sciences", "A quelle temperature l'eau bout-elle au niveau de la mer ?", "100 °C",
     ["100 °C", "90 °C", "110 °C", "0 °C"], "L'ebullition depend aussi de la pression."),
    ("sciences", "Quel organe pompe le sang dans le corps ?", "Le coeur",
     ["Le coeur", "Le poumon", "Le foie", "Le rein"], "Le coeur bat environ 100 000 fois par jour."),
    ("sciences", "Quelle est l'unite de mesure de la force ?", "Le newton",
     ["Le newton", "Le joule", "Le watt", "Le pascal"], "Le joule mesure l'energie, le watt la puissance."),

    # ------------------------------------------------------------------ Maths
    ("maths", "Combien font 7 × 8 ?", "56",
     ["56", "54", "64", "48"], "7 × 8 = 56."),
    ("maths", "Resous l'equation 3x + 5 = 20.", "x = 5",
     ["x = 5", "x = 4", "x = 6", "x = 3"], "3x = 15, donc x = 5."),
    ("maths", "Quelle est l'aire d'un rectangle de 4 cm sur 7 cm ?", "28 cm²",
     ["28 cm²", "11 cm²", "22 cm²", "14 cm²"], "Aire = longueur × largeur = 4 × 7."),
    ("maths", "Combien de degrees mesure un angle droit ?", "90°",
     ["90°", "180°", "360°", "45°"], "Un angle plat mesure 180°, un angle droit la moitie."),
    ("maths", "Quelle est la racine carree de 144 ?", "12",
     ["12", "14", "11", "24"], "12 × 12 = 144."),
    ("maths", "Quel est le terme suivant : 2, 4, 8, 16, ... ?", "32",
     ["32", "24", "20", "30"], "On multiplie chaque terme par 2."),

    # ------------------------------------------------------------------- Code
    ("code", "En Python, quelle fonction donne la longueur d'une liste ?", "len()",
     ["len()", "length()", "size()", "count()"], "len([1, 2, 3]) renvoie 3."),
    ("code", "Quel mot-cle definit une fonction en Python ?", "def",
     ["def", "function", "func", "define"], "Exemple : def ma_fonction(x): ..."),
    ("code", "En JavaScript, comment declarer une constante ?", "const",
     ["const", "let", "var", "static"], "const interdit la reaffectation de la variable."),
    ("code", "En JavaScript, que vaut [1, 2, 3][0] ?", "1",
     ["1", "0", "2", "undefined"], "Les tableaux sont indexes a partir de 0."),
    ("code", "En Python, que vaut 5 // 2 ?", "2",
     ["2", "2.5", "3", "1"], "// est la division entiere (avec 5 / 2 = 2.5)."),
    ("code", "Que fait la methode Python list.append(x) ?", "Ajoute x a la fin",
     ["Ajoute x a la fin", "Supprime x", "Trie la liste", "Compte les x"], "append modifie la liste sur place."),

    # ---------------------------------------------------------------- Histoire
    ("histoire", "En quelle annee a commence la Seconde Guerre mondiale ?", "1939",
     ["1939", "1914", "1945", "1933"], "L'Allemagne attaque la Pologne en septembre 1939."),
    ("histoire", "Quel est le premier president de la Ve Republique ?", "Charles de Gaulle",
     ["Charles de Gaulle", "Napoleon", "Georges Pompidou", "Francois Mitterrand"], "Il est elu en 1958."),
    ("histoire", "En quelle annee commence la Revolution francaise ?", "1789",
     ["1789", "1799", "1848", "1815"], "La prise de la Bastille a lieu le 14 juillet 1789."),
    ("histoire", "Qui a decouvert la penicilline ?", "Alexander Fleming",
     ["Alexander Fleming", "Louis Pasteur", "Marie Curie", "Thomas Edison"], "La decouverte date de 1928."),
    ("histoire", "En quelle annee tombe le mur de Berlin ?", "1989",
     ["1989", "1991", "1985", "2000"], "Le 9 novembre 1989."),
    ("histoire", "Qui a ecrit Les Miserables ?", "Victor Hugo",
     ["Victor Hugo", "Honore de Balzac", "Emile Zola", "Alexandre Dumas"], "Roman publie en 1862."),

    # -------------------------------------------------------------- Geographie
    ("geographie", "Quelle est la capitale du Japon ?", "Tokyo",
     ["Tokyo", "Kyoto", "Osaka", "Seoul"], "Tokyo est aussi la plus grande ville du pays."),
    ("geographie", "Quel est le plus long fleuve de France ?", "La Loire",
     ["La Loire", "La Seine", "Le Rhone", "La Garonne"], "La Loire mesure environ 1 000 km."),
    ("geographie", "Quel ocean borde la Californie ?", "L'ocean Pacifique",
     ["L'ocean Pacifique", "L'ocean Atlantique", "L'ocean Indien", "L'ocean Arctique"], "La cote ouest des USA donne sur le Pacifique."),
    ("geographie", "Quelle est la plus haute montagne du monde ?", "L'Everest",
     ["L'Everest", "Le K2", "Le Kilimandjaro", "Le Mont Blanc"], "L'Everest culmine a 8 848 metres."),
    ("geographie", "Quelle est la capitale du Canada ?", "Ottawa",
     ["Ottawa", "Toronto", "Montreal", "Vancouver"], "Toronto est la plus grande ville, pas la capitale."),
    ("geographie", "Quel pays depasse le Chine en population depuis 2023 ?", "L'Inde",
     ["L'Inde", "Les Etats-Unis", "L'Indonesie", "Le Bresil"], "L'Inde a depasse la Chine selon l'ONU."),

    # ------------------------------------------------------- Culture / Francais
    ("francais", "Quel est le pluriel de « cheval » ?", "chevaux",
     ["chevaux", "chevals", "chevaus", "chevaulx"], "Les noms en -al font souvent -aux."),
    ("francais", "Qui a ecrit Le Petit Prince ?", "Antoine de Saint-Exupery",
     ["Antoine de Saint-Exupery", "Victor Hugo", "Albert Camus", "Jean-Paul Sartre"], "Ouvrage publie en 1943."),
    ("francais", "Combien de lettres compte l'alphabet francais ?", "26",
     ["26", "25", "27", "24"], "Comme l'alphabet latin, avec des accents et ligatures."),
    ("francais", "Quel est le contraire de « clairseme » ?", "dense",
     ["dense", "rare", "mince", "leger"], "Un ensemble dense est serre, opposé a clairsemé."),
    ("francais", "Quel etait le vrai nom de Moliere ?", "Jean-Baptiste Poquelin",
     ["Jean-Baptiste Poquelin", "Pierre Corneille", "Jean Racine", "Voltaire"], "Moliere etait un nom de scene."),
    ("francais", "Qui a peint La Joconde ?", "Leonard de Vinci",
     ["Leonard de Vinci", "Pablo Picasso", "Vincent van Gogh", "Claude Monet"], "Tableau du debut du XVIe siecle."),

    # ------------------------------------------------------------------ Loisirs
    ("loisir", "Combien de cases compte un plateau de Monopoly ?", "40",
     ["40", "32", "36", "48"], "Le plateau classique comporte 40 cases."),
    ("loisir", "Combien de cartes contient un jeu standard sans les jokers ?", "52",
     ["52", "54", "50", "48"], "4 couleurs × 13 valeurs."),
    ("loisir", "Combien de joueurs compte une equipe de football ?", "11",
     ["11", "10", "9", "12"], "Gardien inclus."),
    ("loisir", "Quel sport est pratique aux Jeux olympiques d'hiver ?", "Le ski",
     ["Le ski", "La natation", "L'athletisme", "Le football"], "La natation et l'athletisme sont aux Jeux d'ete."),
    ("loisir", "Combien de faces possede un des classique ?", "6",
     ["6", "4", "8", "12"], "Un de classique est un cube."),
    ("loisir", "Dans quelle serie apparait Mario ?", "Super Mario",
     ["Super Mario", "The Legend of Zelda", "Sonic", "Minecraft"], "Mario est la mascotte de Nintendo."),
]

MOTS_CATEGORIES = {
    "maths": ("math", "calcul", "algebre", "geometrie", "equation", "nombre", "addition",
              "multiplication", "racine", "angle"),
    "code": ("code", "python", "javascript", "programmation", "informatique", "dev",
             "algo", "script", "bug", "fonction"),
    "sciences": ("science", "physique", "chimie", "biologie", "planete", "espace", "atome",
                 "corps humain", "eau", "electricite", "soleil"),
    "histoire": ("histoire", "guerre", "revolution", "president", "siecle", "napoléon",
                 "napoléon", "roi", "date"),
    "geographie": ("geo", "geographie", "capitale", "pays", "ocean", "montagne", "fleuve",
                   "carte", "ville", "continent"),
    "francais": ("francais", "français", "grammaire", "orthographe", "litterature", "livre",
                 "auteur", "poeme", "mot", "peintre"),
    "loisir": ("loisir", "jeu", "sport", "carte", "monopoly", "football", "olympique",
               "devinette", "film", "musique"),
}


def est_demande_quiz(texte):
    """Vrai si le message demande un quiz / questionnaire."""
    return bool(re.search(r"\b(quiz|quizz|questionnaire|test de connaissances)\b",
                          (texte or "").lower()))


def _categorie(texte):
    bas = _norm(texte)
    for cat, mots in MOTS_CATEGORIES.items():
        if any(_norm(m) in bas for m in mots):
            return cat
    return None


def generer(texte, nombre=6):
    """Renvoie un quiz Markdown pret a l'emploi, ou None si aucun sujet ne correspond."""
    if not est_demande_quiz(texte):
        return None
    m = re.search(r"(\d+)\s*(?:questions?|qcm)", (texte or "").lower())
    if m:
        nombre = int(m.group(1))
    nombre = max(3, min(int(nombre or 6), 10))

    cat = _categorie(texte)
    if cat:
        pool = [q for q in BANQUE if q[0] == cat]
        titre = {"maths": "Mathématiques", "code": "Code", "sciences": "Sciences",
                 "histoire": "Histoire", "geographie": "Géographie",
                 "francais": "Culture générale", "loisir": "Loisirs"}[cat]
    else:
        pool = list(BANQUE)
        titre = "Culture générale"

    if not pool:
        return None
    choix = random.sample(pool, min(nombre, len(pool)))

    lignes = [f"## Quiz — {titre} ({len(choix)} questions)", ""]
    corrige = ["## Corrigé", ""]
    lettres = "ABCD"
    for i, (_, question, bonne, propositions, explication) in enumerate(choix, 1):
        options = list(propositions)
        random.shuffle(options)
        index = options.index(bonne)
        lignes.append(f"**{i}. {question}**")
        for j, option in enumerate(options):
            lignes.append(f"{lettres[j]}) {option}")
        lignes.append("")
        corrige.append(f"{i}. **{lettres[index]} — {bonne}** : {explication}")
    lignes += corrige
    return "\n".join(lignes)
