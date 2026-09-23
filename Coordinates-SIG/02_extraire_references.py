#!/usr/bin/env python3
"""Cherche, pour chaque site de sites_bruts.csv, les points OpenStreetMap qui portent un nom proche.

Trois couches sont fouillées : structures de santé, établissements d'enseignement et localités.
Le résultat, sorties/candidats_osm.csv, sert à remplir decisions.csv à la main : le script propose,
il ne tranche pas.

Usage :
  python3 02_extraire_references.py [--sites sites_bruts.csv] [--osm sources_osm]
                                    [--seuil 0.6] [--sortie sorties/candidats_osm.csv]
"""
import argparse
import csv
import difflib
import json
import math
import os
import re
import unicodedata

COUCHES = {
    "sante": "osm_rd_congo_poi_health.geojson",
    "education": "osm_rd_congo_poi_education.geojson",
    "localite": "rd_congo_localities.geojson",
}
# Emprise large de l'Ituri, pour écarter les homonymes du reste du pays.
BBOX = (0.5, 3.6, 27.0, 31.6)  # lat_min, lat_max, lon_min, lon_max

ABREVIATIONS = [
    (r"\bHOPITAL GENERAL DE REFERENCE\b", "HGR"), (r"\bHOPITAL GENERAL\b", "HGR"),
    (r"\bCENTRE DE SANTE DE REFERENCE\b", "CSR"), (r"\bCENTRE DE SANTE\b", "CS"),
    (r"\bPOSTE DE SANTE\b", "PS"), (r"\bCENTRE DE TRAITEMENT EBOLA\b", "CTE"),
    (r"\bCENTRE DE TRANSIT\b", "CT"), (r"\bCENTRE MEDICAL EVANGELIQUE\b", "CME"),
]
MOTS_VIDES = {"DE", "DU", "DES", "LA", "LE", "LES", "L", "D"}
TYPES = {"HGR", "CSR", "CS", "PS", "CTE", "CT", "CME", "ISTM"}


def majuscules(s):
    return unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().upper()


def cles(nom):
    """Renvoie (clé complète, clé sans le type de structure), mots triés."""
    s = " ".join(re.sub(r"[^A-Z0-9 ]", " ", majuscules(nom)).split())
    for motif, abrev in ABREVIATIONS:
        s = re.sub(motif, abrev, s)
    mots = list(dict.fromkeys(m for m in s.split() if m not in MOTS_VIDES))
    if len(mots) > 2 and mots[0] in {"CTE", "CT"}:  # « CTE HGR X » s'apparie avec « HGR X »
        mots = mots[1:]
    base = [m for m in mots if m not in TYPES] or mots
    return " ".join(sorted(mots)), " ".join(sorted(base))


def score(a, b):
    """Similarité pénalisée quand les deux noms portent des types de structure différents."""
    r = difflib.SequenceMatcher(None, a, b).ratio()
    ta, tb = set(a.split()) & TYPES, set(b.split()) & TYPES
    return r * 0.85 if ta and tb and not ta & tb else r


def distance_m(la1, lo1, la2, lo2):
    p1, p2 = math.radians(la1), math.radians(la2)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lo2 - lo1) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))


def charger(chemin):
    points = []
    with open(chemin, encoding="utf-8") as f:
        for element in json.load(f)["features"]:
            p = element["properties"]
            nom = p.get("name")
            if not nom:
                continue
            lat, lon = p.get("lat"), p.get("lon")
            g = element.get("geometry") or {}
            if lat is None and g.get("type") == "Point":
                lon, lat = g["coordinates"][:2]
            if lat is None:
                continue
            lat, lon = float(lat), float(lon)
            if not (BBOX[0] <= lat <= BBOX[1] and BBOX[2] <= lon <= BBOX[3]):
                continue
            ident = f"way/{p['osm_way_id']}" if p.get("osm_way_id") else f"node/{p.get('osm_id')}"
            k, base = cles(nom)
            points.append({"nom": nom, "id": ident, "lat": lat, "lon": lon, "cle": k, "base": base})
    return points


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sites", default="sites_bruts.csv")
    ap.add_argument("--osm", default="sources_osm")
    ap.add_argument("--seuil", type=float, default=0.6)
    ap.add_argument("--par-site", type=int, default=3, help="nombre de candidats gardés par site")
    ap.add_argument("--sortie", default="sorties/candidats_osm.csv")
    a = ap.parse_args()

    couches = {}
    for nom, fichier in COUCHES.items():
        chemin = os.path.join(a.osm, fichier)
        if not os.path.exists(chemin):
            raise SystemExit(f"{chemin} manquant : lance d'abord 01_telecharger_osm.sh")
        couches[nom] = charger(chemin)
        print(f"{nom}: {len(couches[nom])} points nommés dans l'emprise Ituri")

    with open(a.sites, encoding="utf-8") as f:
        sites = list(csv.DictReader(f))

    os.makedirs(os.path.dirname(a.sortie) or ".", exist_ok=True)
    lignes = []
    for s in sites:
        if not s["site"].strip():
            continue
        cle, base = cles(s["site"])
        lat = float(s["latitude"]) if s["latitude"] else None
        lon = float(s["longitude"]) if s["longitude"] else None
        candidats = []
        for couche, points in couches.items():
            champ = "base" if couche == "localite" else "cle"
            reference = base if couche == "localite" else cle
            for p in points:
                sc = score(reference, p[champ])
                if sc >= a.seuil:
                    candidats.append({
                        "zone_sante": s["zone_sante"], "site": s["site"], "couche": couche,
                        "nom_osm": p["nom"], "osm_id": p["id"],
                        "latitude_osm": round(p["lat"], 6), "longitude_osm": round(p["lon"], 6),
                        "score_nom": round(sc, 2),
                        "distance_m": round(distance_m(lat, lon, p["lat"], p["lon"])) if lat is not None else "",
                    })
        candidats.sort(key=lambda c: (-c["score_nom"], c["distance_m"] if c["distance_m"] != "" else 1e9))
        lignes.extend(candidats[:a.par_site])

    with open(a.sortie, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(lignes[0].keys()))
        w.writeheader()
        w.writerows(lignes)
    print(f"\n{len(lignes)} candidats écrits dans {a.sortie}")
    print("Les retenus sont reportés à la main dans decisions.csv.")


if __name__ == "__main__":
    main()
