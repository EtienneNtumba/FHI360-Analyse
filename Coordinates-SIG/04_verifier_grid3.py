#!/usr/bin/env python3
"""Compare les coordonnées retenues aux couches GRID3 (zones de santé, structures de santé).

Pour chaque site :
  - la zone de santé du polygone qui contient le point est-elle celle déclarée ?
  - quelle structure GRID3 de la même zone porte le nom le plus proche, et à quelle distance ?
  - pour un site sans coordonnées, GRID3 propose-t-il une position ?

Usage :
  python3 04_verifier_grid3.py --sites sorties/coordonnees_ituri.csv \
      --zones <couche zones de santé> --champ-zone <colonne du nom de zone> \
      --fosa <couche structures de santé> --champ-nom <colonne du nom de structure> \
      --sortie sorties/coordonnees_ituri_verifiees.csv

Sans --champ-zone ou --champ-nom, le script affiche les colonnes disponibles et s'arrête.
Formats acceptés : GeoPackage, GeoJSON, Shapefile ; CSV pour les structures (--fosa-lat, --fosa-lon).
"""
import argparse
import difflib
import math
import re
import sys
import unicodedata

import geopandas as gpd
import pandas as pd

ABREVIATIONS = [
    (r"\bHOPITAL GENERAL DE REFERENCE\b", "HGR"), (r"\bHOPITAL GENERAL\b", "HGR"),
    (r"\bCENTRE DE SANTE DE REFERENCE\b", "CSR"), (r"\bCENTRE DE SANTE\b", "CS"),
    (r"\bPOSTE DE SANTE\b", "PS"), (r"\bCENTRE DE TRAITEMENT EBOLA\b", "CTE"),
    (r"\bCENTRE DE TRANSIT\b", "CT"), (r"\bCENTRE MEDICAL EVANGELIQUE\b", "CME"),
]
MOTS_VIDES = {"DE", "DU", "DES", "LA", "LE", "LES", "L", "D"}
TYPES = {"HGR", "CSR", "CS", "PS", "CTE", "CT", "CME"}


def majuscules(s):
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().upper().strip()


def cle_zone(s):
    s = re.sub(r"^(ZONE DE SANTE|ZS)\s+", "", majuscules(s))
    return re.sub(r"[^A-Z0-9]", "", s)


def cle_nom(s):
    s = " ".join(re.sub(r"[^A-Z0-9 ]", " ", majuscules(s)).split())
    for motif, abrev in ABREVIATIONS:
        s = re.sub(motif, abrev, s)
    mots = list(dict.fromkeys(m for m in s.split() if m not in MOTS_VIDES))
    if len(mots) > 2 and mots[0] in {"CTE", "CT"}:  # "CTE HGR X" s'apparie avec "HGR X"
        mots = mots[1:]
    return " ".join(sorted(mots))


def similarite(a, b):
    """Similarité des noms normalisés, pénalisée si les types de structure diffèrent (CSR contre HGR, etc.)."""
    score = difflib.SequenceMatcher(None, a, b).ratio()
    ta, tb = set(a.split()) & TYPES, set(b.split()) & TYPES
    return score * 0.85 if ta and tb and not ta & tb else score


def distance_m(la1, lo1, la2, lo2):
    p1, p2 = math.radians(la1), math.radians(la2)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lo2 - lo1) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))


def lire_couche(chemin, lat, lon):
    if chemin.lower().endswith(".csv"):
        df = pd.read_csv(chemin)
        if lat not in df.columns or lon not in df.columns:
            sys.exit(f"{chemin} : indique --fosa-lat et --fosa-lon parmi {list(df.columns)}")
        return gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df[lon], df[lat]), crs="EPSG:4326")
    couche = gpd.read_file(chemin)
    return couche.to_crs("EPSG:4326") if couche.crs else couche.set_crs("EPSG:4326")


def exiger_champ(champ, couche, option):
    if not champ or champ not in couche.columns:
        sys.exit(f"Indique --{option} parmi : {[c for c in couche.columns if c != 'geometry']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sites", required=True)
    ap.add_argument("--col-lat", default="latitude_retenue", help="colonne de latitude à contrôler")
    ap.add_argument("--col-lon", default="longitude_retenue", help="colonne de longitude à contrôler")
    ap.add_argument("--zones", required=True)
    ap.add_argument("--champ-zone")
    ap.add_argument("--fosa", required=True)
    ap.add_argument("--champ-nom")
    ap.add_argument("--fosa-lat", default="latitude")
    ap.add_argument("--fosa-lon", default="longitude")
    ap.add_argument("--seuil-nom", type=float, default=0.85, help="similarité minimale des noms (0 à 1)")
    ap.add_argument("--seuil-ecart", type=float, default=300, help="écart toléré avec GRID3, en mètres")
    ap.add_argument("--sortie", default="sorties/coordonnees_ituri_verifiees.csv")
    a = ap.parse_args()

    zones = lire_couche(a.zones, None, None)
    exiger_champ(a.champ_zone, zones, "champ-zone")
    zones = zones[[a.champ_zone, "geometry"]].rename(columns={a.champ_zone: "zone_poly"})

    fosa = lire_couche(a.fosa, a.fosa_lat, a.fosa_lon)
    exiger_champ(a.champ_nom, fosa, "champ-nom")
    fosa = fosa[[a.champ_nom, "geometry"]].rename(columns={a.champ_nom: "nom_grid3"})
    fosa["geometry"] = fosa.geometry.representative_point()
    fosa = gpd.sjoin(fosa, zones, how="left", predicate="within")
    fosa = fosa[~fosa.index.duplicated()].reset_index(drop=True)
    fosa["cle_zone"] = fosa["zone_poly"].map(lambda z: cle_zone(z) if pd.notna(z) else "")
    fosa["cle_nom"] = fosa["nom_grid3"].map(cle_nom)

    sites = pd.read_csv(a.sites, dtype=str, keep_default_na=False)
    lat = pd.to_numeric(sites[a.col_lat], errors="coerce")
    lon = pd.to_numeric(sites[a.col_lon], errors="coerce")
    avec = lat.notna() & lon.notna()
    points = gpd.GeoDataFrame(index=sites.index[avec], crs="EPSG:4326",
                              geometry=gpd.points_from_xy(lon[avec], lat[avec]))
    points = gpd.sjoin(points, zones, how="left", predicate="within")
    points = points[~points.index.duplicated()]
    sites["zone_polygone"] = points["zone_poly"].reindex(sites.index).fillna("")

    resultats = []
    for i, s in sites.iterrows():
        candidats = fosa[fosa["cle_zone"] == cle_zone(s["zone_sante"])]
        nom, score, g_lat, g_lon = "", 0.0, None, None
        if s["site"].strip() and len(candidats):
            cle = cle_nom(s["site"])
            scores = candidats["cle_nom"].map(lambda c: similarite(cle, c))
            j = scores.idxmax()
            nom, score = candidats.at[j, "nom_grid3"], float(scores[j])
            g_lat, g_lon = candidats.at[j, "geometry"].y, candidats.at[j, "geometry"].x
        apparie = score >= a.seuil_nom
        ecart = distance_m(lat[i], lon[i], g_lat, g_lon) if (avec[i] and apparie) else None
        zone_ok = bool(s["zone_polygone"]) and cle_zone(s["zone_polygone"]) == cle_zone(s["zone_sante"])

        if not s["site"].strip():
            verdict = "site non nommé : obtenir le nom"
        elif not avec[i]:
            verdict = "position proposée par GRID3, à confirmer" if apparie else "relevé terrain nécessaire"
        elif not zone_ok:
            verdict = "hors de la zone déclarée : vérifier"
        elif not apparie:
            verdict = "non apparié à GRID3 : vérifier le nom ou relever sur place"
        elif ecart <= a.seuil_ecart:
            verdict = "concordant avec GRID3"
        else:
            verdict = "divergent : comparer sur imagerie satellite"

        resultats.append({
            "zone_ok": zone_ok if avec[i] else "",
            "grid3_meilleur_candidat": nom,
            "grid3_score_nom": round(score, 2) if nom else "",
            "grid3_apparie": apparie if nom else "",
            "grid3_latitude": round(g_lat, 6) if apparie else "",
            "grid3_longitude": round(g_lon, 6) if apparie else "",
            "ecart_m": round(ecart) if ecart is not None else "",
            "verdict": verdict,
        })

    sortie = pd.concat([sites, pd.DataFrame(resultats, index=sites.index)], axis=1)
    import os
    os.makedirs(os.path.dirname(a.sortie) or ".", exist_ok=True)
    sortie.to_csv(a.sortie, index=False, encoding="utf-8-sig")
    print(sortie["verdict"].value_counts().to_string())
    print(f"\nRésultat écrit dans {a.sortie}")


if __name__ == "__main__":
    main()
