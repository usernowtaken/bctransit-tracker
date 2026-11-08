"""Conservative, offline fleet lookup for BC Transit Bus Radar V3.0 Alpha.

IMPORTANT:
- A four-digit suffix in a Victoria VehicleDescriptor.label is a *candidate*,
  not a GTFS-guaranteed physical fleet ID. Preserve the raw label.
- Range membership is not proof that the bus is currently active, nor does it
  verify which physical vehicle is transmitting the ID.
- Never apply Victoria-specific label conventions to other transit systems.
- Fleet build years determine the NovaBus generation; individual roof variants
  remain verified per fleet number rather than inferred from a whole batch.
- The supplied Gen 2/Gen 3 drawings are artwork fallbacks, not a literal
  declaration of the physical bus's generation.
"""
from __future__ import annotations
import re
from typing import Any

# Manual public fleet-series references (no network requests in the app):
#   https://barp.ca/bus/bctransit/victoria/index.html
#   https://www.bctransit.com/about/fleet/
#   https://www.showbus.com/galcanada/BC_Transit_Enviro500MMC.htm
# BC Transit production cohorts, cross-checked with its operator documentation
# and model-year photo listings. Gen 3 spans 2009–2012; Gen 4 starts in 2013.
# The supplied Gen 2 illustration remains the *neutral artwork fallback* for
# 2009 models with unverified roof type. Gen 4 uses the supplied Gen 3 drawing
# because no Gen 4 artwork was supplied. Do not claim those drawings are exact.
# Body/roof reference observations tied to specific *physical fleet numbers*.
# GPS cannot determine a roof shape. Only add observations grounded in photos
# or a published fleet record; do not extrapolate from the production year.
# 9287, 9303, 9426: user-provided photos (November 2026).
# 9434: 2012 Smart Bus prototype with full-length roof fairings:
# https://www.barp.ca/bus/bctransit/victoria/2015lfs/2015lfs.html
NOVA_BODY_REFERENCES: dict[str, dict[str, str]] = {
    '9287': {'variant': 'flat', 'basis': 'Photograph supplied by the project owner'},
    '9303': {'variant': 'flat', 'basis': 'Photograph supplied by the project owner'},
    '9426': {'variant': 'raised', 'basis': 'Photograph supplied by the project owner'},
    '9434': {'variant': 'smart', 'basis': 'Barp Victoria fleet gallery; 2012 Smart Bus prototype'},
}


def nova_body_for(fleet_number: str) -> dict[str, str] | None:
    """Photo-verified body variant; unknown vehicles deliberately return None."""
    variant = NOVA_BODY_REFERENCES.get(str(fleet_number))
    return dict(variant) if variant else None

# [start, end, model_key, display name, classification note]
VICTORIA_FLEET_SERIES: tuple[tuple[int,int,str,str,str], ...] = (
    (1148, 1277, 'xn40', 'New Flyer XN40', 'Victoria 2019–25 XN40 series'),
    (7500, 7526, 'xe40', 'New Flyer XE40', 'Victoria XE40 units 7500–7526; 7525/7526 observed in live fleet listings'),
    (7527, 7599, 'generic', '75xx electric bus (model not yet catalogued)', '75xx fleet number recognized; exact model requires an independent roster match'),
    (4062, 4073, 'vicinity30', "Vicinity 30′", 'Victoria 2017–18 30-foot series'),
    (4200, 4248, 'vicinity30', "Vicinity 30′ CNG", 'Victoria 2020–22 30-foot CNG series'),
    (9201, 9289, 'nova2', 'NovaBus LFS Gen 2 (2006–2008)', 'Early second-generation offset-drive LFS; Gen 2 drawing'),
    (9290, 9318, 'nova2', 'NovaBus LFS Gen 2 (2008)', 'Late second-generation LFS; Gen 2 drawing'),
    (9319, 9433, 'nova2', 'NovaBus LFS Gen 3 (2009)', 'Third-generation T-drive; artwork follows verified individual roof shape'),
    (9434, 9434, 'nova3', 'NovaBus LFS Smart Bus (2012 prototype)', 'Third-generation prototype with full-length roof fairings; HEV not verified'),
    (9435, 9446, 'nova3', 'NovaBus LFS Gen 4 (2013)', 'Fourth-generation T-drive; uses supplied Gen 3 drawing as fallback'),
    (9447, 9486, 'nova3', 'NovaBus LFS Gen 4 (2015)', 'Fourth-generation T-drive; uses supplied Gen 3 drawing as fallback'),
    (6000, 6029, 'generic', 'NovaBus LFS Gen 4 (2017)', 'Fourth-generation T-drive; exact supplied artwork unavailable'),
    (9041, 9049, 'enviro500', 'Alexander Dennis Enviro500', 'Victoria early Enviro500 series'),
    (9501, 9531, 'enviro500', 'Alexander Dennis Enviro500', 'Victoria 2008 and demonstrator series'),
    (9532, 9589, 'enviro500mmc', 'Alexander Dennis Enviro500 MMC', 'Victoria 2020–26 MMC series'),
)
MODEL_IMAGES = frozenset({'xn40','xe40','vicinity30','nova2','nova3','enviro500','enviro500mmc','generic'})

# Only the fixed prefix explicitly seen in the user's Victoria live snapshot.
# We do NOT suffix-strip arbitrary numeric labels from other agencies.
VICTORIA_FEED_LABEL = re.compile(r'^313135(\d{4})$')
FOUR_DIGITS = re.compile(r'^\d{4}$')


def series_for(fleet_number: str) -> dict[str, str] | None:
    if not FOUR_DIGITS.fullmatch(fleet_number):
        return None
    number = int(fleet_number)
    for low, high, key, name, note in VICTORIA_FLEET_SERIES:
        if low <= number <= high:
            result = {'model_key': key, 'model': name, 'series_note': note}
            if (9201 <= number <= 9318):
                result['nova_generation'] = 2
            elif (9319 <= number <= 9434):
                result['nova_generation'] = 3
            elif (9435 <= number <= 9486) or (6000 <= number <= 6029):
                result['nova_generation'] = 4
            return result
    return None


def identify_vehicle(system_id: str, label: Any) -> dict[str, Any]:
    """Return bounded safe metadata, never an unqualified confirmed fleet ID."""
    result = {'fleet_number': None, 'fleet_status': 'unavailable',
              'fleet_basis': None, 'model_key': 'generic', 'model': None,
              'model_basis': None}
    if system_id != 'victoria' or not isinstance(label, str):
        return result
    clean = label.strip()
    match = VICTORIA_FEED_LABEL.fullmatch(clean)
    # Four digits supplied as an explicit GTFS label are a stronger signal than
    # a suffix, but still not independently verified against a painted fleet ID.
    direct = FOUR_DIGITS.fullmatch(clean)
    candidate = match.group(1) if match else clean if direct else None
    if not candidate:
        return result
    series = series_for(candidate)
    if series is None:
        # Unknown number? Do NOT claim a fleet identity from an arbitrary suffix.
        return result
    result.update(fleet_number=candidate, fleet_status='candidate',
                  fleet_basis='Victoria feed label (' + ('four-digit' if direct else 'recognized suffix') + ')',
                  model=series['model'], model_key=series['model_key'],
                  model_basis='Published Victoria fleet-series range; ' + series['series_note'])
    if 'nova_generation' in series:
        result['nova_generation'] = series['nova_generation']
    body = nova_body_for(candidate)
    if body:
        result.update(nova_body_variant=body['variant'], nova_body_basis=body['basis'])
    if candidate == '9434':
        # A verified exception, without introducing any new bus artwork.
        result['model'] = 'NovaBus LFS Smart Bus (2012 prototype)'
        result['model_basis'] = '2012 LFS Smart Bus prototype; Barp Victoria documents full-length roof fairings; HEV not established'
        result['nova_special'] = 'smart_lfs_9434'
    return result
