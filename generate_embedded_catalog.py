"""
============================================================
  Exoplanet Explorer — Generate Embedded Star Catalog
  src/preprocessing/generate_embedded_catalog.py

  Reads the processed catalog, selects a diverse set of
  stars with proper 3D positions, and writes a clean
  JavaScript file (embedded_catalog.js) that the HTML
  frontend includes directly — no fetch(), no CORS issues.

  Usage:
      python src/preprocessing/generate_embedded_catalog.py

  Output:
      frontend/embedded_catalog.js
============================================================
"""

import csv
import json
import math
import random
from pathlib import Path

random.seed(42)

ROOT     = Path(__file__).parent.parent.parent
DATA_DIR = ROOT / 'data'
OUT_PATH = ROOT / 'frontend' / 'embedded_catalog.js'


# ── STAR COLOR FROM TEMPERATURE ───────────────────────────────────────────────
def teff_to_color(teff: float) -> str:
    """Blackbody approximation — matches spectral class color."""
    if   teff > 25000: return '#9bb0ff'   # O — deep blue
    elif teff > 10000: return '#aabfff'   # B — blue-white
    elif teff > 7500:  return '#cad7ff'   # A — white-blue
    elif teff > 6000:  return '#f8f7ff'   # F — pure white
    elif teff > 5200:  return '#fff4ea'   # G — warm white (Sun-like)
    elif teff > 3700:  return '#ffd2a1'   # K — orange
    else:              return '#ffcc6f'   # M — red-orange


# ── FIBONACCI SPHERE — even distribution ──────────────────────────────────────
def fibonacci_sphere(i: int, n: int, r_min: float = 8, r_max: float = 80) -> tuple:
    """
    Places point i of n on a sphere using the Fibonacci lattice.
    Produces the most evenly distributed sphere points possible.
    r_min/r_max control the depth range in scene units.
    """
    golden = math.pi * (3 - math.sqrt(5))
    y      = 1 - (i / max(n - 1, 1)) * 2
    radius = math.sqrt(max(1 - y * y, 0))
    theta  = golden * i
    # Distance increases with index so nearby stars are closer to origin
    r      = r_min + (r_max - r_min) * (i / n) ** 0.6
    return (
        round(r * radius * math.cos(theta), 2),
        round(r * y, 2),
        round(r * radius * math.sin(theta), 2),
    )


# ── PLANET TYPE FROM RADIUS ───────────────────────────────────────────────────
def planet_type(radius: float) -> str:
    if   radius < 0.8:  return 'Sub-Earth'
    elif radius < 1.25: return 'Earth-size'
    elif radius < 2.0:  return 'Super-Earth'
    elif radius < 4.0:  return 'Sub-Neptune'
    elif radius < 10.0: return 'Neptune-size'
    elif radius < 15.0: return 'Saturn-size'
    else:               return 'Jupiter-size'


# ── LOAD PROCESSED CATALOG ────────────────────────────────────────────────────
def load_catalog() -> list[dict]:
    path = DATA_DIR / 'exoplanets_processed.csv'
    if not path.exists():
        print(f"  [warn] {path} not found — using synthetic catalog")
        return []

    by_star = {}
    with open(path, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            host = row.get('hostname', '').strip()
            if not host:
                continue

            def flt(k, default=0.0):
                try:    return float(row.get(k) or default)
                except: return default

            teff    = flt('st_teff', 5778)
            st_mass = flt('st_mass', 1.0)
            st_rad  = flt('st_rad',  1.0)
            st_lum  = flt('st_lum',  0.0)
            dist    = max(flt('sy_dist', 200), 1.0)

            # Habitable zone (Kopparapu 2013)
            L   = 10 ** st_lum
            T   = teff - 5780
            hz_in  = math.sqrt(L / 1.107) * (1 - 2.77e-5*T - 1.38e-9*T**2)
            hz_out = math.sqrt(L / 0.356)  * (1 - 1.33e-5*T - 3.86e-9*T**2)
            hz_in  = max(0.05, hz_in)
            hz_out = max(hz_in + 0.01, hz_out)

            pl_rad   = max(flt('pl_rade',  1.0), 0.1)
            pl_smax  = max(flt('pl_orbsmax', 1.0), 0.001)
            pl_per   = max(flt('pl_orbper', 365.0), 0.1)
            pl_eqt   = flt('pl_eqt', 255.0)
            pl_insol = flt('pl_insol', 1.0)
            method   = row.get('discoverymethod', 'Transit').strip()
            disc_yr  = int(flt('disc_year', 2015))
            pl_name  = row.get('pl_name', host + ' b').strip()

            in_hz    = hz_in <= pl_smax <= hz_out
            is_rocky = pl_rad < 1.8

            r_norm = 1 - abs(pl_rad - 1.0) / (pl_rad + 1.0)
            t_norm = 1 - abs(pl_eqt - 288)  / (pl_eqt + 288)
            esi    = round(max(r_norm * t_norm, 0) ** 0.5, 3)
            hab    = round(
                (0.4 if in_hz else 0) +
                (0.3 if is_rocky else 0) +
                esi * 0.3, 3
            )
            plaus  = round(min(1.0, 0.6 + (0.1 if is_rocky else 0) + (0.1 if in_hz else 0)), 3)

            planet = {
                'name':        pl_name,
                'period':      round(pl_per, 1),
                'radius':      round(pl_rad, 3),
                'smax':        round(pl_smax, 4),
                'eqt':         round(pl_eqt, 1),
                'insol':       round(pl_insol, 3),
                'method':      method,
                'year':        disc_yr,
                'type':        planet_type(pl_rad),
                'in_hz':       in_hz,
                'is_rocky':    is_rocky,
                'plausibility': plaus,
                'habitability': hab,
                'esi':         esi,
            }

            if host not in by_star:
                by_star[host] = {
                    'id':       host,
                    'name':     host,
                    'teff':     round(teff, 0),
                    'color':    teff_to_color(teff),
                    'st_mass':  round(st_mass, 2),
                    'st_rad':   round(st_rad, 2),
                    'dist_pc':  round(dist, 1),
                    'hz_in':    round(hz_in, 3),
                    'hz_out':   round(hz_out, 3),
                    'planets':  [],
                    '_max_hab': 0,
                    '_has_hz':  False,
                }
            by_star[host]['planets'].append(planet)
            if hab > by_star[host]['_max_hab']:
                by_star[host]['_max_hab'] = hab
            if in_hz:
                by_star[host]['_has_hz'] = True

    stars = list(by_star.values())
    for s in stars:
        s['max_hab']   = s.pop('_max_hab')
        s['has_hz']    = s.pop('_has_hz')
        s['n_planets'] = len(s['planets'])
    return stars


# ── SELECT DIVERSE SAMPLE ─────────────────────────────────────────────────────
def select_stars(stars: list[dict], n: int = 300) -> list[dict]:
    """
    Select a diverse set stratified across habitability score
    so the 3D view shows a mix of interesting and ordinary stars.
    """
    high = [s for s in stars if s['max_hab'] > 0.7]
    mid  = [s for s in stars if 0.4 < s['max_hab'] <= 0.7]
    low  = [s for s in stars if s['max_hab'] <= 0.4]

    # Proportional sampling
    n_high = min(len(high), n // 3)
    n_mid  = min(len(mid),  n // 3)
    n_low  = min(len(low),  n - n_high - n_mid)

    random.shuffle(high); random.shuffle(mid); random.shuffle(low)
    selected = high[:n_high] + mid[:n_mid] + low[:n_low]
    random.shuffle(selected)
    return selected


# ── ASSIGN 3D POSITIONS ───────────────────────────────────────────────────────
def assign_positions(stars: list[dict]) -> list[dict]:
    """
    Assign clean 3D positions using the Fibonacci sphere algorithm.
    Closer stars (lower dist_pc) get lower sphere indices so they
    appear nearer to the Solar System origin.
    """
    # Sort by distance so closer stars cluster near origin
    stars = sorted(stars, key=lambda s: s['dist_pc'])
    n = len(stars)

    for i, s in enumerate(stars):
        x, y, z = fibonacci_sphere(i, n, r_min=6, r_max=85)
        s['x'] = x
        s['y'] = y
        s['z'] = z

    return stars


# ── WRITE JAVASCRIPT FILE ─────────────────────────────────────────────────────
def write_js(stars: list[dict], path: Path):
    """
    Writes a self-contained JS file that sets window.EMBEDDED_CATALOG.
    The HTML simply includes this with a <script> tag — no fetch needed.
    """
    # Strip hz_in/hz_out from top level (only needed internally)
    clean = []
    for s in stars:
        c = {k: v for k, v in s.items() if k not in ('hz_in', 'hz_out')}
        clean.append(c)

    js_data = json.dumps(clean, separators=(',', ':'))

    js = f"""// ============================================================
//  Exoplanet Explorer — Embedded Star Catalog
//  Auto-generated by generate_embedded_catalog.py
//  {len(clean)} stars · Diverse habitability · Fibonacci sphere positions
//  Re-run generate_embedded_catalog.py to refresh
// ============================================================
window.EMBEDDED_CATALOG = {js_data};
"""
    path.parent.mkdir(exist_ok=True)
    path.write_text(js)

    size_kb = path.stat().st_size / 1024
    print(f"  Written → {path}  ({size_kb:.0f} KB, {len(clean)} stars)")


# ── SYNTHETIC FALLBACK (if no CSV available) ──────────────────────────────────
def synthetic_catalog(n: int = 300) -> list[dict]:
    """
    Generates a realistic synthetic catalog when the processed CSV
    is not available. Uses published exoplanet occurrence distributions.
    """
    STAR_TYPES = [
        {'type':'G', 'teff':5778, 'mass':1.00, 'lum': 0.00, 'freq':0.20},
        {'type':'K', 'teff':4500, 'mass':0.75, 'lum':-0.45, 'freq':0.28},
        {'type':'M', 'teff':3300, 'mass':0.35, 'lum':-1.30, 'freq':0.38},
        {'type':'F', 'teff':6500, 'mass':1.30, 'lum': 0.35, 'freq':0.10},
        {'type':'A', 'teff':8500, 'mass':1.80, 'lum': 0.90, 'freq':0.04},
    ]
    METHODS  = ['Transit'] * 7 + ['Radial Velocity'] * 2 + ['Imaging']
    PREFIXES = ['Kepler', 'KIC', 'HD', 'TOI', 'GJ', 'HIP', 'TYC', 'Wolf']

    def rng(seed): 
        x = math.sin(seed) * 43758.5453
        return x - math.floor(x)

    stars = []
    for i in range(n):
        # Pick star type weighted by frequency
        r = rng(i * 7)
        cum = 0
        st = STAR_TYPES[0]
        for t in STAR_TYPES:
            cum += t['freq']
            if r < cum:
                st = t
                break

        L       = 10 ** st['lum']
        dist    = 20 + rng(i * 3) * 480
        teff    = st['teff'] + (rng(i * 5) - 0.5) * 400
        color   = teff_to_color(teff)

        # HZ
        T      = teff - 5780
        hz_in  = max(0.05, math.sqrt(L / 1.107) * (1 - 2.77e-5*T - 1.38e-9*T**2))
        hz_out = max(hz_in + 0.01, math.sqrt(L / 0.356) * (1 - 1.33e-5*T - 3.86e-9*T**2))

        n_pl   = 1 + int(rng(i * 11) * 4)
        planets, max_hab, has_hz = [], 0, False

        for j in range(n_pl):
            smax    = 0.05 + rng(i * 29 + j * 7) * 3.0
            rad     = 0.4  + rng(i * 31 + j * 3) * 9.0
            albedo  = 0.3 if rad < 1.8 else 0.5
            eqt     = 278 * L**0.25 * (1-albedo)**0.25 / math.sqrt(max(smax, 0.001))
            insol   = L / max(smax**2, 0.001)
            period  = 365.25 * (smax**1.5) / st['mass']**0.5
            in_hz   = hz_in <= smax <= hz_out
            is_rocky= rad < 1.8
            r_n     = 1 - abs(rad - 1) / (rad + 1)
            t_n     = 1 - abs(eqt - 288) / (eqt + 288)
            esi     = round(max(r_n * t_n, 0)**0.5, 3)
            hab     = round((0.4 if in_hz else 0) + (0.3 if is_rocky else 0) + esi * 0.3, 3)
            plaus   = round(min(1, 0.6 + (0.1 if is_rocky else 0) + (0.1 if in_hz else 0)), 3)
            name_prefix = PREFIXES[i % len(PREFIXES)]
            star_num    = int(rng(i * 13) * 9000) + 1000

            planets.append({
                'name':         f"{name_prefix}-{star_num} {chr(98+j)}",
                'period':       round(period, 1),
                'radius':       round(rad, 3),
                'smax':         round(smax, 4),
                'eqt':          round(eqt, 1),
                'insol':        round(insol, 3),
                'method':       METHODS[i % len(METHODS)],
                'year':         2009 + int(rng(i * 37 + j) * 16),
                'type':         planet_type(rad),
                'in_hz':        in_hz,
                'is_rocky':     is_rocky,
                'plausibility': plaus,
                'habitability': hab,
                'esi':          esi,
            })
            if hab > max_hab: max_hab = hab
            if in_hz:         has_hz  = True

        prefix = PREFIXES[i % len(PREFIXES)]
        num    = int(rng(i * 13) * 9000) + 1000
        name   = f"{prefix}-{num}"
        stars.append({
            'id':       name, 'name': name,
            'teff':     round(teff, 0), 'color': color,
            'st_mass':  round(st['mass'] + (rng(i*43)-0.5)*0.1, 2),
            'st_rad':   round(0.5 + rng(i*47) * 1.5, 2),
            'dist_pc':  round(dist, 1),
            'n_planets': n_pl,
            'max_hab':  max_hab, 'has_hz': has_hz,
            'planets':  planets,
        })
    return stars


# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    print("\n" + "═"*50)
    print("  Generate Embedded Star Catalog")
    print("═"*50)

    print("\n  [1/3] Loading catalog...")
    stars = load_catalog()

    if stars:
        print(f"         {len(stars)} host stars loaded from CSV")
        print("\n  [2/3] Selecting diverse sample...")
        stars = select_stars(stars, n=300)
    else:
        print("         Using synthetic catalog")
        stars = synthetic_catalog(n=300)

    print(f"         {len(stars)} stars selected")
    print(f"         Colors: {len(set(s['color'] for s in stars))} distinct")
    print(f"         HZ stars: {sum(1 for s in stars if s['has_hz'])}")
    print(f"         Hab range: {min(s['max_hab'] for s in stars):.2f} – {max(s['max_hab'] for s in stars):.2f}")

    print("\n  [3/3] Assigning 3D positions (Fibonacci sphere)...")
    stars = assign_positions(stars)
    xs = [s['x'] for s in stars]
    ys = [s['y'] for s in stars]
    zs = [s['z'] for s in stars]
    print(f"         X: {min(xs):.1f} to {max(xs):.1f}")
    print(f"         Y: {min(ys):.1f} to {max(ys):.1f}")
    print(f"         Z: {min(zs):.1f} to {max(zs):.1f}")

    write_js(stars, OUT_PATH)

    print("\n  Done.")
    print(f"  Add to your HTML before the closing </body>:")
    print(f"  <script src=\"embedded_catalog.js\"></script>")
    print("═"*50 + "\n")


if __name__ == '__main__':
    main()
