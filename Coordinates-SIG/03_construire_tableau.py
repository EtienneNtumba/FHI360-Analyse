#!/usr/bin/env python3
"""Assemble sites_bruts.csv et decisions.csv en un tableau unique de coordonnées.

Chaque ligne garde la valeur d'origine et reçoit une valeur retenue, sa source, sa fiabilité
et l'écart entre les deux quand les deux existent.

Usage :
  python3 03_construire_tableau.py [--sites sites_bruts.csv] [--decisions decisions.csv]
                                   [--sortie sorties/coordonnees_ituri.csv]

Actions possibles dans decisions.csv :
  garder     la valeur d'origine est retenue ; la référence, si elle est renseignée, sert de contrôle
  remplacer  la référence remplace la valeur d'origine
  completer  la référence remplit une case vide
  relever    aucune valeur : à relever sur le terrain ou à demander au bureau central de zone
"""
import argparse
import csv
import math
import os
import re
import unicodedata

A_RELEVER = "à relever ou à demander au BCZ"


def majuscules(s):
    return unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().upper()


def type_site(nom):
    mots = re.sub(r"[^A-Z0-9 ]", " ", majuscules(nom)).split()
    if not mots:
        return ""
    if "CTE" in mots or "TRAITEMENT" in mots:
        return "CTE"
    for t in ("CT", "HGR", "CSR", "CS", "PS"):
        if t in mots:
            return t
    return "à préciser"


def distance_m(la1, lo1, la2, lo2):
    p1, p2 = math.radians(la1), math.radians(la2)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lo2 - lo1) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))


def lire(chemin):
    with open(chemin, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sites", default="sites_bruts.csv")
    ap.add_argument("--decisions", default="decisions.csv")
    ap.add_argument("--sortie", default="sorties/coordonnees_ituri.csv")
    a = ap.parse_args()

    decisions = {(d["zone_sante"].strip().title(), d["site"].strip()): d for d in lire(a.decisions)}
    lignes = []
    for s in lire(a.sites):
        zone = s["zone_sante"].strip().title()
        site = s["site"].strip()
        d = decisions.get((zone, site))
        if d is None:
            raise SystemExit(f"Décision manquante pour {zone} / {site or '(sans nom)'}")

        action = d["action"].strip()
        lat, lon = s["latitude"].strip(), s["longitude"].strip()
        ref_lat, ref_lon = d["ref_latitude"].strip(), d["ref_longitude"].strip()
        reference = " ".join(x for x in (d["ref_source"].strip(), d["ref_id"].strip()) if x)

        if action in ("remplacer", "completer"):
            retenue, source = (ref_lat, ref_lon), reference or "référence non précisée"
        elif action == "garder":
            retenue = (lat, lon)
            source = "liste d'origine" + (f" ; contrôlée sur {reference}" if reference else "")
        elif action == "relever":
            retenue, source = ("", ""), A_RELEVER
        else:
            raise SystemExit(f"Action inconnue pour {site} : {action}")

        ecart = ""
        if lat and ref_lat:
            ecart = round(distance_m(float(lat), float(lon), float(ref_lat), float(ref_lon)))

        lignes.append({
            "province": "Ituri",
            "zone_sante": zone,
            "zone_sante_origine": s["zone_sante"],
            "site": site,
            "type": type_site(site),
            "latitude": lat,
            "longitude": lon,
            "latitude_retenue": retenue[0],
            "longitude_retenue": retenue[1],
            "source_retenue": source,
            "fiabilite": d["fiabilite"].strip(),
            "action": action,
            "reference_utilisee": reference,
            "ecart_origine_reference_m": ecart,
            "commentaire": d["commentaire"].strip(),
            "source_terrain": "",
            "date_releve": "",
        })

    os.makedirs(os.path.dirname(a.sortie) or ".", exist_ok=True)
    with open(a.sortie, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(lignes[0].keys()))
        w.writeheader()
        w.writerows(lignes)

    avec = sum(1 for l in lignes if l["latitude_retenue"])
    compte = {}
    for l in lignes:
        compte[l["action"]] = compte.get(l["action"], 0) + 1
    print(f"{len(lignes)} lignes écrites dans {a.sortie}")
    print(f"{avec} avec coordonnée retenue, {len(lignes) - avec} à relever")
    print("actions :", ", ".join(f"{k} {v}" for k, v in sorted(compte.items())))


if __name__ == "__main__":
    main()
