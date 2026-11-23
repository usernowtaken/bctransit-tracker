"""Conservative, offline fleet lookup for BC Transit Bus Radar V3.4.11.

IMPORTANT:
- A four-digit suffix in a Victoria VehicleDescriptor.label is a *candidate*,
  not a GTFS-guaranteed physical fleet ID. Preserve the raw label.
- Range membership is not proof that the bus is currently active, nor does it
  verify which physical vehicle is transmitting the ID.
- Regional ten-digit descriptor IDs can yield *candidate* fleet matches only
  when using a bounded BC Transit-looking prefix and regional model series.
  This is not independent proof that the physical bus carries that number.
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
# Regional fleet identifiers are model-series candidates, NOT proof of a current
# depot allocation. Narrow per-unit entries take priority over production-wide
# fallbacks. Never guess the exact body/paint/roof photograph from a prefix.
#
# References (unit/production family):
#   BC Transit fleet-maintenance public bus lists (Kelowna 3007/3011/3012,
#   Chilliwack 4439–4441); BC Transit fleet overview; busdrawings.com regional
#   photo galleries (Kelowna 6000–6029, 9319–9433; Chilliwack 9211–9231,
#   9447–9486); TransSee real-time regional listings (only current examples).
# See REGIONAL-FLEETS.md for source links and uncertainties.
# 70xx Kelowna electric fleet classification remains provisional by vehicle;
# LFSe+ is not guaranteed just because a label begins with 70.
# Note: Chilliwack/FVX data can include Abbotsford/Mission vehicles.
REGIONAL_FLEET_SERIES: dict[str, tuple[tuple[int,int,str,str,str], ...]] = {
    'kelowna': (
        # Historical named units: avoid treating the entire 30xx/44xx group
        # as located in Kelowna, since other BC systems use the same numbers.
        (3007, 3007, 'vicinity_2013', 'Grande West / Yaxing Vicinity (2013)', 'Historically assigned to Kelowna in BC Transit bus list; no supplied photo of this early variant'),
        (3011, 3012, 'vicinity_2013', 'Grande West / Yaxing Vicinity (2013)', 'Historically assigned to Kelowna in BC Transit bus list; no supplied photo of this early variant'),
        (4400, 4400, 'vicinity35', "Grande West Vicinity 35′ (2017)", 'Reported Kelowna unit, regional allocation not independently confirmed; no accurate 35-foot image supplied'),
        (4403, 4403, 'vicinity35', "Grande West Vicinity 35′ (2017)", 'Reported Kelowna unit, regional allocation not independently confirmed; no accurate 35-foot image supplied'),
        (2922, 2922, 'light_duty', "ARBOC Spirit of Freedom 27′ (2024)", 'Photographed operating in Kelowna; no supplied ARBOC artwork'),
        (2700, 2999, 'light_duty', 'Light-duty community bus (exact model unverified)', 'Mixed light-duty series; identify ARBOC/Blue Bird per unit, not by whole-number family; artwork unavailable'),
        (6000, 6029, 'nova3', 'NovaBus LFS Gen 4 (2017)', '2017 Kelowna LFS cohort; Gen 3 drawing is a user-requested fallback, not Gen 4 exact artwork'),
        (7000, 7039, 'nova_lfse', 'NovaBus LFSe+ (provisional 70xx electric series)', 'Provisional model-family guess; Kelowna electric buses confirmed in service; per-unit manufacturer/model not independently verified'),
        (9201, 9231, 'nova2', 'NovaBus LFS Gen 2 (2006)', '2006 provincial production cohort, individual depot assignment may change'),
        (9232, 9267, 'nova2', 'NovaBus LFS Gen 2 (2007)', '2007 provincial production cohort, individual depot assignment may change'),
        (9268, 9318, 'nova2', 'NovaBus LFS Gen 2 (2008)', '2008 provincial production cohort, individual depot assignment may change'),
        (9319, 9433, 'nova3', 'NovaBus LFS Gen 3 (2009)', '2009 provincial production cohort; supplied reference drawing is not per-unit roof verification'),
        (9435, 9446, 'nova3', 'NovaBus LFS Gen 4 (2013)', '2013 provincial production cohort; Kelowna assignment unconfirmed; Gen 3 drawing is a user-requested fallback'),
        (9447, 9486, 'nova3', 'NovaBus LFS Gen 4 (2015)', '2015 provincial production cohort; Kelowna assignment unconfirmed; Gen 3 reference art is a user-requested visual fallback'),
    ),
    'chilliwack': (
        # The Chilliwack / FVX group includes Abbotsford/Mission services.
        (1148, 1277, 'xn40', 'New Flyer XN40 CNG (Central Fraser Valley)', 'Abbotsford/Mission CNG model series; not all vehicles are assigned there'),
        (4200, 4248, 'vicinity30cng', "Vicinity 30′ CNG (Central Fraser Valley)", 'Abbotsford/Mission CNG Vicinity series including observed 4232–4233; exact art not supplied'),
        (3005, 3005, 'vicinity_2013', 'Grande West / Yaxing Vicinity (2013)', 'Historical Chilliwack photo record; no early Vicinity drawing supplied'),
        (4034, 4034, 'vicinity30', "Grande West Vicinity 30′ (2017)", 'Photo documented in Chilliwack/Agassiz/Harrison operation; supplied 30-foot drawing is a model reference'),
        (4060, 4073, 'vicinity30', "Grande West Vicinity 30′ (2017–2018)", 'Provincial production family; regional allocation varies'),
        (4401, 4402, 'vicinity35', "Grande West Vicinity 35′ (2017)", 'Recorded Chilliwack units; no supplied accurate 35-foot image'),
        (4439, 4441, 'vicinity35', "Grande West Vicinity 35′ (2018)", 'BC Transit Chilliwack fleet-maintenance bus lists; no supplied accurate 35-foot image'),
        (4400, 4474, 'vicinity35', "Grande West Vicinity 35′", 'Provincial production family only; allocation to Chilliwack is unverified; no 35-foot artwork supplied'),
        (2700, 2999, 'light_duty', 'Light-duty community bus (exact model unverified)', 'ARBOC/Blue Bird/other small bus; cannot identify exact body without per-vehicle roster'),
        (9201, 9231, 'nova2', 'NovaBus LFS Gen 2 (2006)', '2006 provincial production cohort; allocation can vary'),
        (9232, 9267, 'nova2', 'NovaBus LFS Gen 2 (2007)', '2007 provincial production cohort; allocation can vary'),
        (9268, 9318, 'nova2', 'NovaBus LFS Gen 2 (2008)', '2008 provincial production cohort; allocation can vary'),
        (9319, 9433, 'nova3', 'NovaBus LFS Gen 3 (2009)', '2009 provincial production cohort; allocation can vary; individual roof unknown'),
        (9435, 9446, 'nova3', 'NovaBus LFS Gen 4 (2013)', '2013 production cohort; regional allocation uncertain; no supplied Gen 4 art'),
        (9447, 9486, 'nova3', 'NovaBus LFS Gen 4 (2015)', '2015 NovaBus LFS cohort, includes photographed FVX units; no supplied Gen 4 art'),
    ),    'cowichan': (
        # Cowichan Valley operator 10 includes the 66/99 Victoria commuter
        # routes and route 70 to Nanaimo. Observed per-unit examples are
        # earlier than / separate from broad provincial production models.
        (2842, 2844, 'light_duty', 'ARBOC light-duty bus (2022; exact subtype unverified)',
         'BC Transit 23C21 2023 fleet-maintenance list: 2842–2844 at Cowichan Valley Conventional; no ARBOC image supplied'),
        (2700, 2999, 'light_duty', 'Light-duty / community bus (model unverified)',
         'Mixed light-duty provincial series; verify ARBOC and other body types individually; artwork unavailable'),
        (4013, 4013, 'vicinity30', "Grande West Vicinity 30′ (2017)",
         'Cowichan 2017 unit in BC Transit 23C24 bus list'),
        (4017, 4023, 'vicinity30', "Grande West Vicinity 30′ (2017)",
         '2017 provincial 30-foot Vicinity series; 4017/4019/4020 active sightings in Cowichan and several units listed in BC Transit records; allocations can change'),
        (4025, 4025, 'vicinity30', "Grande West Vicinity 30′ (2017)",
         'Cowichan unit documented in BC Transit 23C24 fleet list'),
        (4007, 4061, 'vicinity30', "Grande West Vicinity 30′ (2017)",
         '2017 provincial 30-foot Vicinity production series; not evidence every unit is based in Cowichan'),
        (4432, 4432, 'vicinity35', "Grande West Vicinity 35′ (2017)",
         'Cowichan 4432 documented in vehicle video and BC Transit maintenance records; no 35-foot illustration supplied'),
        (4471, 4474, 'vicinity35', "Grande West Vicinity 35′ (2018)",
         'BC Transit 23C24 maintenance list and Cowichan bus photo gallery; no 35-foot illustration supplied'),
        (4400, 4432, 'vicinity35', "Grande West Vicinity 35′ (2017)",
         'Provincial model production family; Cowichan allocation unverified for most numbers'),
        (4433, 4474, 'vicinity35', "Grande West Vicinity 35′ (2018)",
         'Provincial model production family; Cowichan allocation unverified for most numbers'),
        (9290, 9300, 'nova2', 'NovaBus LFS Gen 2 Suburban (2008)',
         'Cowichan commuter vehicles 9294/9295/9297/9300 documented via photos and 2026 tracker; suburban-style body, supplied Gen 2 artwork is reference'),
        (9201, 9231, 'nova2', 'NovaBus LFS Gen 2 (2006)',
         'Provincial series only; individual Cowichan assignment unverified'),
        (9232, 9267, 'nova2', 'NovaBus LFS Gen 2 (2007)',
         'Provincial series only; individual Cowichan assignment unverified'),
        (9268, 9318, 'nova2', 'NovaBus LFS Gen 2 (2008)',
         'Provincial series only; individual Cowichan assignment unverified'),
        (9319, 9433, 'nova3', 'NovaBus LFS Gen 3 (2009)',
         'Provincial series only; individual Cowichan assignment unverified'),
        (9435, 9446, 'nova3', 'NovaBus LFS Gen 4 (2013)',
         'Provincial model series only; no Gen 4 artwork supplied; Cowichan assignment unverified'),
        (9447, 9486, 'nova3', 'NovaBus LFS Gen 4 (2015)',
         'Provincial model series only; no Gen 4 artwork supplied; Cowichan assignment unverified'),
    ),

}
MODEL_IMAGES = frozenset({'xn40','xe40','vicinity30','vicinity30cng','vicinity35','vicinity_2013','nova2','nova3','nova_lfse','light_duty','enviro500','enviro500mmc','generic'})


def regional_series_for(system_id: str, fleet_number: str) -> dict[str, str] | None:
    if not FOUR_DIGITS.fullmatch(fleet_number):
        return None
    n = int(fleet_number)
    for low, high, key, name, note in REGIONAL_FLEET_SERIES.get(system_id, ()):
        if low <= n <= high:
            series = {'model_key': key, 'model': name, 'series_note': note}
            if key == 'nova2': series['nova_generation'] = 2
            elif key == 'nova3': series['nova_generation'] = 4 if (n >= 9435 or 6000 <= n <= 6029) else 3
            return series
    return None


# Only the fixed prefix explicitly seen in the user's Victoria live snapshot.
# We do NOT suffix-strip arbitrary numeric labels from other agencies.
VICTORIA_FEED_LABEL = re.compile(r'^313135(\d{4})$')
# Limited provisional regional decoding. A 10-digit string with 3131xx as
# its prefix resembles a feed label observed in the BC Transit family, but
# is not guaranteed by GTFS-RT. Confirm the suffix belongs to this region's
# documented model series, preserve the raw label, and mark as a candidate.
REGIONAL_FEED_LABEL = re.compile(r'^3131\d{2}(\d{4})$')
# Some providers publish an explicit display label instead of bare digits.
EXPLICIT_FLEET_LABEL = re.compile(r'^(?:bus|fleet|vehicle)\s*#?\s*(\d{4})$', re.I)
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


def _candidate_from_label(system_id: str, clean: str) -> tuple[str | None, str | None]:
    """Interpret only an explicit number or a bounded BC Transit-looking label."""
    if FOUR_DIGITS.fullmatch(clean):
        return clean, 'direct four-digit label'
    explicit = EXPLICIT_FLEET_LABEL.fullmatch(clean)
    if explicit:
        return explicit.group(1), 'explicitly labelled fleet number'
    if system_id == 'victoria':
        match = VICTORIA_FEED_LABEL.fullmatch(clean)
        return (match.group(1), 'observed Victoria numeric label') if match else (None, None)
    match = REGIONAL_FEED_LABEL.fullmatch(clean)
    return (match.group(1), 'provisional BC Transit ten-digit label') if match else (None, None)


def identify_vehicle(system_id: str, label: Any) -> dict[str, Any]:
    """Return candidate (not confirmed) fleet information, using scoped rosters."""
    result = {'fleet_number': None, 'fleet_status': 'unavailable',
              'fleet_basis': None, 'model_key': 'generic', 'model': None,
              'model_basis': None}
    if system_id not in ('victoria', 'kelowna', 'chilliwack', 'cowichan') or not isinstance(label, str):
        return result
    clean = label.strip()
    candidate, kind = _candidate_from_label(system_id, clean)
    if not candidate:
        return result
    series = series_for(candidate) if system_id == 'victoria' else regional_series_for(system_id, candidate)
    if series is None:
        return result
    result.update(fleet_number=candidate, fleet_status='candidate',
                  fleet_basis=system_id.title() + ' ' + kind + ' (candidate; not independently verified)',
                  model=series['model'], model_key=series['model_key'],
                  model_basis='BC Transit fleet-series reference; ' + series['series_note'])
    if 'nova_generation' in series:
        result['nova_generation'] = series['nova_generation']
    body = nova_body_for(candidate) if system_id == 'victoria' else None
    if body:
        result.update(nova_body_variant=body['variant'], nova_body_basis=body['basis'])
    if system_id == 'victoria' and candidate == '9434':
        result['model'] = 'NovaBus LFS Smart Bus (2012 prototype)'
        result['model_basis'] = '2012 LFS Smart Bus prototype; Barp Victoria documents full-length roof fairings; HEV not established'
        result['nova_special'] = 'smart_lfs_9434'
    return result


def identify_feed_vehicle(system_id: str, label: Any, descriptor_id: Any) -> dict[str, Any]:
    """Use a genuine fleet label, or a four-digit descriptor ID as a fallback.

    Never interpret arbitrary numeric suffixes or trip IDs as a fleet number.
    The raw ID is a *candidate* only if it matches a documented model series.
    """
    primary = identify_vehicle(system_id, label)
    if primary.get('fleet_number'):
        return primary
    # The GTFS-RT vehicle descriptor may omit `label` while including a
    # ten-digit ID that has the same recognisable structure. The older code
    # checked only a bare four-digit descriptor ID, leaving regional buses
    # unidentified even if the ID ended with a roster-listed fleet number.
    # `id` is NOT a trip ID; app.parse_vehicle_feed supplies descriptor.id or
    # entity.id only. Restrict both formats to the system's roster and keep
    # identification provisional.
    if isinstance(descriptor_id, str):
        clean_id = descriptor_id.strip()
        direct = FOUR_DIGITS.fullmatch(clean_id)
        patterned = (VICTORIA_FEED_LABEL.fullmatch(clean_id) if system_id == 'victoria'
                     else REGIONAL_FEED_LABEL.fullmatch(clean_id))
        if direct or patterned:
            secondary = identify_vehicle(system_id, clean_id)
            if secondary.get('fleet_number'):
                kind = 'four-digit' if direct else 'bounded ten-digit'
                secondary['fleet_basis'] = (system_id.title() + ' ' + kind +
                       ' vehicle descriptor/entity ID (unverified fleet candidate)')
                return secondary
    return primary
