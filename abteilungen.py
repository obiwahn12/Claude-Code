"""Zutaten den Bring!-Abteilungen zuordnen (für die gegliederte Einkaufsliste).

Reihenfolge: 1. Bring!-Katalog (Standardartikel), 2. eigene feste Zuordnung für Zutaten,
die Bring! nicht kennt, 3. Stichworte im Namen, 4. sonst „Eigene Artikel“ – wie in der Bring!-App.
"""

import bring

EIGENE_ARTIKEL = "Eigene Artikel"
# Reihenfolge wie in der Bring!-App, falls der Katalog nicht geladen werden kann
STANDARD_REIHENFOLGE = [
    "Obst & Gemüse", "Brot & Gebäck", "Milch & Käse", "Fleisch & Fisch", "Zutaten & Gewürze",
    "Fertig- & Tiefkühlprodukte", "Getreideprodukte", "Snacks & Süsswaren", "Getränke", "Haushalt",
    "Pflege & Gesundheit", "Tierbedarf", "Baumarkt & Garten",
]

OG, BG, MK, FF = "Obst & Gemüse", "Brot & Gebäck", "Milch & Käse", "Fleisch & Fisch"
ZG, FT, GP, SS, GT = "Zutaten & Gewürze", "Fertig- & Tiefkühlprodukte", "Getreideprodukte", "Snacks & Süsswaren", "Getränke"

# Zutaten aus den Rezepten, die nicht im Bring!-Katalog stehen.
# Vegetarische/vegane Alternativen stehen bei „Fleisch & Fisch“ (wie Salami in Bring!).
ZUORDNUNG = {
    OG: ["Salatgurke", "Möhren", "Blattspinat", "Babyspinat", "Limetten", "Avocados", "Weißkohl", "Rotkohl",
         "Kirschtomaten", "Suppengrün", "Pak Choi", "Maiskolben", "Schmorgurken", "Feldsalat", "Rosenkohl",
         "Minze", "Dill", "Auberginen", "Hokkaido-Kürbis"],
    BG: ["Wraps", "Tortillas", "Ciabatta", "Flammkuchenteig", "Strudelteig", "Naan", "Hot-Dog-Brötchen",
         "Burgerbrötchen", "Toast", "Toasties", "Rosinenbrötchen"],
    MK: ["Haferdrink", "Soja-Sahne", "Geriebener Käse", "Saure Sahne", "Halloumi", "Vanillesoße", "Camembert",
         "Ziegenkäse", "Grillkäse", "Crème fraîche", "Ofenkäse", "Cheddar-Scheiben", "Vegane Butter", "Skyr",
         "Gouda", "Emmentaler"],
    FF: ["Veggi-Chicken", "Vegetarische Würstchen", "Räuchertofu", "Soja-Hack", "Vegetarische Bratwurst",
         "Veggi-Döner", "Vegetarische Rouladen", "Vegane Würstchen", "Veggie-Burger-Patties",
         "Vegetarische Schnitzel"],
    ZG: ["Gemüsebrühe", "Muskat", "Passierte Tomaten", "Gehackte Tomaten", "Kidneybohnen", "Gewürzgurken",
         "Kreuzkümmel", "Currypulver", "Sesam", "Pflaumenmus", "Preiselbeeren", "Noriblätter", "Taco-Gewürz",
         "Hefeflocken", "Pesto", "Lorbeerblätter", "Röstzwiebeln", "Majoran", "Rosinen", "Würfelzucker", "Mohn",
         "Sonnenblumenkerne", "Meersalz", "Wasabi", "Sweet-Chili-Sauce", "Dressing", "Brechbohnen", "Kala Namak",
         "Kurkuma", "Grillsoße", "Garam Masala", "Crispy Chili Öl", "Erdnussbutter", "Leinöl", "Remoulade",
         "Burger-Sauce", "Kräuter der Provence", "Sauce Hollandaise", "Kümmel", "Rote Currypaste", "Dosen-Mais",
         "Chili-Flocken", "Kürbiskerne", "Kürbiskernöl", "Weiße Bohnen", "Schwarze Bohnen",
         "Paprikapulver geräuchert", "Bohnenkraut", "Miso-Paste", "Sesamöl"],
    FT: ["TK-Kräuter", "Rahmspinat", "Falafel", "Hummus", "TK-Gemüse", "Asia-Gemüse", "Kartoffelklöße", "Edamame",
         "Tortelloni Spinat-Ricotta", "Schupfnudeln", "Pommes", "Tortellini", "Spätzle"],
    GP: ["Milchreis", "Weichweizengrieß", "Sushireis", "Jasminreis", "Quinoa", "Makkaroni", "Udon-Nudeln",
         "Rote Linsen", "Cannelloni", "Lasagneplatten", "Bandnudeln", "Berglinsen", "Reisnudeln", "Schälerbsen",
         "Suppennudeln", "Ramen-Nudeln"],
    SS: ["Tortilla-Chips", "Cashewkerne"],
}

# Stichworte für neue Zutaten (geprüft in dieser Reihenfolge, Teil des Namens, klein geschrieben)
STICHWORTE = [
    ("tk-", FT), ("tiefkühl", FT),
    ("vegetarisch", FF), ("vegan", FF), ("veggi", FF), ("tofu", FF), ("soja-hack", FF),
    ("drink", MK), ("milch", MK), ("sahne", MK), ("joghurt", MK), ("quark", MK), ("käse", MK), ("butter", MK),
    ("brötchen", BG), ("teig", BG), ("brot", BG), ("baguette", BG),
    ("nudeln", GP), ("reis", GP), ("linsen", GP), ("pasta", GP), ("haferflocken", GP),
    ("soße", ZG), ("sauce", ZG), ("paste", ZG), ("gewürz", ZG), ("pulver", ZG), ("öl", ZG), ("essig", ZG),
    ("dose", ZG), ("bohnen", ZG), ("mehl", ZG), ("zucker", ZG),
    ("saft", GT), ("wasser", GT), ("bier", GT), ("wein", GT), ("limo", GT),
    ("chips", SS), ("schoko", SS), ("kekse", SS), ("nüsse", SS), ("kerne", SS),
    ("tomaten", OG), ("salat", OG), ("kohl", OG), ("gurke", OG), ("zwiebel", OG), ("kartoffel", OG),
    ("pilze", OG), ("beeren", OG), ("äpfel", OG), ("birnen", OG), ("paprika", OG), ("kräuter", OG),
]


def zuordner(locale="de-DE"):
    """Gibt (abteilung(name) -> str, reihenfolge: list[str]) zurück."""
    katalog = bring.load_catalog(locale)
    namen = bring.load_names(locale)  # interner Schlüssel -> Anzeigename
    karte = {}
    for s in katalog:
        for item in s["items"]:
            for n in (item, namen.get(item, "")):
                if n:
                    karte.setdefault(n.casefold(), s["name"])
    for abt, liste in ZUORDNUNG.items():
        for n in liste:
            karte.setdefault(n.casefold(), abt)
    reihenfolge = [s["name"] for s in katalog] or STANDARD_REIHENFOLGE

    def abteilung(name):
        key = name.strip().casefold()
        if key in karte:
            return karte[key]
        for wort, abt in STICHWORTE:
            if wort in key:
                return abt
        return EIGENE_ARTIKEL

    return abteilung, reihenfolge + [EIGENE_ARTIKEL]
