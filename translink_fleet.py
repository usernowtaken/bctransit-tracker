"""Metro Vancouver fleet production-cohort lookup. Roster matches are candidates,
not verified live physical assignments. Artwork references are independent of model keys.
Sources and confidence notes: VANCOUVER-FLEET-AUDIT.md.
"""
import re
# start, end, model key, model name, build/order year(s), supplied art id, qualification
SERIES = (
    (701, 706, 'tl_lfs', 'NovaBus LFS — Blue Bus', '2007', 'tl_lfs_westvan', ''),
    (901, 909, 'tl_lfs', 'NovaBus LFS — Blue Bus', '2009', 'tl_lfs_westvan', ''),
    (1201, 1217, 'tl_xd40', 'New Flyer XD40 — Blue Bus', '2012', 'tl_xd40_westvan', ''),
    (1601, 1614, 'tl_xd40', 'New Flyer XD40 — Blue Bus', '2016', 'tl_xd40_westvan', ''),
    (2101, 2199, 'tl_e40', 'New Flyer E40LFR trolleybus', '2005–07', 'tl_e40', ''),
    (2201, 2289, 'tl_e40', 'New Flyer E40LFR trolleybus', '2005–07', 'tl_e40', ''),
    (2501, 2540, 'tl_e60', 'New Flyer E60LFR articulated trolleybus', '2007–08', 'tl_e60', ''),
    (2541, 2574, 'tl_e60', 'New Flyer E60LFR articulated trolleybus', '2009', 'tl_e60', ''),
    (3309, 3358, 'tl_c40lfr', 'New Flyer C40LFR CNG', '2006', None, 'Historical production series; not evidence of current service'),
    (7447, 7499, 'tl_d40lfr', 'New Flyer D40LFR', '2006', None, 'Historical production series; not evidence of current service'),
    (7501, 7504, 'tl_d40lfr', 'New Flyer D40LFR', '2006', None, 'Historical production series; not evidence of current service'),
    (8102, 8117, 'tl_d60lfr', 'New Flyer D60LFR', '2007', None, 'Historical production series; not evidence of current service'),
    (8118, 8156, 'tl_de60', 'New Flyer DE60LFR hybrid', '2009–10', 'tl_de60', ''),
    (9201, 9276, 'tl_orion', 'Orion V suburban', '2001', None, 'Historical production series; not evidence of current service'),
    (9277, 9285, 'tl_orion', 'Orion V suburban', '2007–08', None, 'Historical production series; not evidence of current service'),
    (9401, 9499, 'tl_lfshev', 'NovaBus LFS HEV (early generation)', '2008–09', 'tl_lfshev', 'HEV artwork is a family reference; early roof/body may differ'),
    (9501, 9542, 'tl_lfshev', 'NovaBus LFS HEV (early generation)', '2009–10', 'tl_lfshev', 'HEV artwork is a family reference; early roof/body may differ'),
    (9543, 9581, 'tl_lfs', 'NovaBus LFS Gen 3 diesel', '2009–10', 'tl_lfs_gen3', ''),
    (9583, 9590, 'tl_lfs', 'NovaBus LFS Gen 3 diesel', '2009–10', 'tl_lfs_gen3', ''),
    (9605, 9699, 'tl_lfs', 'NovaBus LFS Gen 2 diesel', '2007', 'tl_lfs_gen2', ''),
    (9701, 9725, 'tl_lfs', 'NovaBus LFS Gen 2 diesel', '2007', 'tl_lfs_gen2', ''),
    (9726, 9791, 'tl_lfs', 'NovaBus LFS Gen 2 diesel', '2008', 'tl_lfs_gen2', ''),
    (9797, 9799, 'tl_lfs', 'NovaBus LFS Gen 2 diesel', '2008', 'tl_lfs_gen2', ''),
    (12001, 12025, 'tl_xde60', 'New Flyer XDE60 hybrid articulated', '2012–13', 'tl_xde60', 'Conventional reference; individual livery may differ'),
    (14001, 14045, 'tl_xn40', 'New Flyer XN40 CNG', '2014', 'tl_xn40', ''),
    (15001, 15021, 'tl_xde60', 'New Flyer XDE60 hybrid articulated', '2015', 'tl_xde60', 'Conventional reference; individual livery may differ'),
    (16001, 16051, 'tl_xn40', 'New Flyer XN40 CNG', '2016', 'tl_xn40', ''),
    (16101, 16130, 'tl_xd40', 'New Flyer XD40 diesel', '2016', 'tl_xd40', ''),
    (16131, 16136, 'tl_xd40', 'New Flyer XD40 diesel (former CMBC series)', '2016', 'tl_xd40_westvan', 'Transferred to Blue Bus; old ID may remain in records; no unverified renumbering'),
    (16137, 16137, 'tl_xd40', 'New Flyer XD40 diesel', '2016', 'tl_xd40', ''),
    (16138, 16140, 'tl_xd40', 'New Flyer XD40 diesel (former CMBC series)', '2016', 'tl_xd40_westvan', 'Transferred to Blue Bus; old ID may remain in records; no unverified renumbering'),
    (16201, 16226, 'tl_xde60', 'New Flyer XDE60 hybrid articulated', '2016', 'tl_xde60', 'Conventional reference; individual livery may differ'),
    (16501, 16562, 'tl_girardin', 'Girardin G5 community shuttle', '2016', 'tl_girardin', ''),
    (16601, 16605, 'tl_xd40', 'New Flyer XD40 — Blue Bus', '2016', 'tl_xd40_westvan', '166xx provider ID; physical number not independently verified'),
    (17501, 17505, 'tl_arboc', 'ARBOC Spirit of Mobility', '2017', 'tl_arboc', 'Historical cohort; may have been retired'),
    (17506, 17564, 'tl_girardin', 'Girardin G5 community shuttle', '2017', 'tl_girardin', ''),
    (18001, 18063, 'tl_xde60', 'New Flyer XDE60 hybrid articulated', '2018–19', 'tl_xde60_rapidbus', 'RapidBus production-cohort livery reference; not verified per unit'),
    (18101, 18206, 'tl_xn40', 'New Flyer XN40 CNG', '2017–18', 'tl_xn40', ''),
    (18301, 18404, 'tl_lfshev', 'NovaBus LFS HEV (later generation)', '2018', 'tl_lfshev', ''),
    (18451, 18473, 'tl_lfssub', 'NovaBus LFS Suburban', '2018', 'tl_lfssub', ''),
    (18501, 18509, 'tl_arboc', 'ARBOC Spirit of Mobility', '2018', 'tl_arboc', 'Historical cohort; may have been retired'),
    (18510, 18527, 'tl_girardin', 'Girardin G5 community shuttle', '2018', 'tl_girardin', ''),
    (19001, 19047, 'tl_xde60', 'New Flyer XDE60 hybrid articulated', '2019', 'tl_xde60_rapidbus', 'RapidBus production-cohort livery reference; not verified per unit'),
    (19101, 19147, 'tl_xn40', 'New Flyer XN40 CNG', '2019–20', 'tl_xn40', ''),
    (19301, 19302, 'tl_lfse_legacy', 'NovaBus LFSe (pilot)', '2019', None, 'Historical trial; not LFSe+; no matching supplied art'),
    (19303, 19304, 'tl_xe40', 'New Flyer XE40 (pilot)', '2019', None, 'Historical trial; no Vancouver-specific art'),
    (19401, 19432, 'tl_enviro', 'Alexander Dennis Enviro500 MMC', '2019', 'tl_enviro', ''),
    (19501, 19549, 'tl_arboc', 'ARBOC Spirit of Mobility', '2019', 'tl_arboc', 'Historical cohort; may have been retired'),
    (19550, 19554, 'tl_girardin', 'Girardin G5 community shuttle', '2019', 'tl_girardin', ''),
    (21001, 21025, 'tl_xde60', 'New Flyer XDE60 hybrid articulated', '2021', 'tl_xde60', 'Conventional reference; individual livery may differ'),
    (21401, 21425, 'tl_enviro', 'Alexander Dennis Enviro500 MMC', '2021', 'tl_enviro', ''),
    (21501, 21562, 'tl_arboc', 'ARBOC Spirit of Freedom', '2020–21', 'tl_arboc', ''),
    (22001, 22005, 'tl_xde60', 'New Flyer XDE60 hybrid articulated', '2022–23', 'tl_xde60', 'Reported standard-livery sub-batch; individual livery may differ'),
    (22006, 22015, 'tl_xde60', 'New Flyer XDE60 hybrid articulated', '2022–23', 'tl_xde60_rapidbus', 'Reported RapidBus-livery sub-batch; individual livery may differ'),
    (23001, 23015, 'tl_xde60', 'New Flyer XDE60 hybrid articulated', '2023', 'tl_xde60', 'Conventional reference; individual livery may differ'),
    (23201, 23215, 'tl_lfse', 'NovaBus LFSe+', '2023', 'tl_lfse', ''),
    (23601, 23606, 'tl_girardin', 'Girardin G5 community shuttle', '2023', 'tl_girardin', ''),
    (23651, 23665, 'tl_girardin', 'Girardin G5 community shuttle', '2023', 'tl_girardin', ''),
    (24001, 24016, 'tl_xde60', 'New Flyer XDE60 hybrid articulated', '2023–24', 'tl_xde60', 'Conventional reference; individual livery may differ'),
    (24101, 24150, 'tl_lfscng', 'NovaBus LFS CNG', '2024', 'tl_lfscng', ''),
    (24501, 24548, 'tl_arboc', 'ARBOC Spirit of Freedom', '2024', 'tl_arboc', ''),
    (24601, 24634, 'tl_girardin', 'Girardin G5 community shuttle', '2024', 'tl_girardin', ''),
    (25101, 25184, 'tl_lfscng', 'NovaBus LFS CNG', '2025', 'tl_lfscng', ''),
    (25201, 25207, 'tl_lfse', 'NovaBus LFSe+', '2025', 'tl_lfse', ''),
    (25501, 25527, 'tl_arboc', 'ARBOC Spirit of Freedom', '2025', 'tl_arboc', ''),
    (25601, 25627, 'tl_girardin', 'Girardin G5 community shuttle', '2025', 'tl_girardin', ''),
    (26101, 26130, 'tl_lfscng', 'NovaBus LFS CNG', '2026', 'tl_lfscng', '2026 batch has revised livery; drawing is a model reference'),
    (26601, 26624, 'tl_girardin', 'Girardin G5 community shuttle', '2026', 'tl_girardin', ''),
    (27001, 27001, 'tl_solaris12', 'Solaris Trollino 12 (pilot)', '2026', 'tl_solaris12', 'Pilot only; subsequent production numbers not assumed'),
    (28201, 28201, 'tl_solaris18', 'Solaris Trollino 18 (pilot)', '2026', 'tl_solaris18', 'Reported pilot; live service not independently established'),

)
# Precompute immutable fleet-number lookup at import; no network access per vehicle.
ROSTER = {}
for first,last,key,model,year,art,note in SERIES:
    for n in range(first,last+1):
        if n in ROSTER: raise ValueError(f'Overlapping fleet series: {n}')
        ROSTER[n]=(key,model,year,art,note)
BLUE_BUS_ALIASES = {80000+n:n for first,last in ((701,706),(901,909),(1201,1217)) for n in range(first,last+1)}
PATTERN=re.compile(r'^(?:BUS\s*#?\s*|FLEET\s*#?\s*|[BHPRSV]\s*)?(\d{3,5})$',re.I)

def identify(label, descriptor_id=None):
    result={'fleet_number':None,'fleet_status':'unavailable','fleet_basis':None,'model_key':'generic','model':None,'model_basis':None}
    for raw,field in ((label,'label'),(descriptor_id,'descriptor ID')):
        if not isinstance(raw,str): continue
        match=PATTERN.fullmatch(raw.strip())
        if not match: continue
        n=int(match.group(1)); alias=n in BLUE_BUS_ALIASES; n=BLUE_BUS_ALIASES.get(n,n)
        series=ROSTER.get(n)
        if not series: continue
        key,model,year,art,note=series
        basis=f'TransLink {field}; '+('documented Blue Bus ID alias; ' if alias else '')+'roster candidate, not verified'
        return {**result,'fleet_number':str(n),'fleet_status':'candidate','fleet_basis':basis,'model_key':key,'model':f'{model} ({year})','model_year':year,'fleet_art_id':art,'model_basis':'Published fleet cohort; '+(note or 'actual assignment and livery unverified')}
    if isinstance(label,str):
        match=PATTERN.fullmatch(label.strip())
        if match and int(match.group(1))>=100:
            return {**result,'fleet_number':match.group(1),'fleet_status':'candidate','fleet_basis':'Numeric display label; physical fleet identity unverified','model_basis':'No matching production cohort'}
    return result
