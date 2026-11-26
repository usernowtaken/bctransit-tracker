"""Preliminary production-cohort model hints; not a verified active roster."""
import re
# Explicit ranges from the planning roster; gaps remain unknown.
SERIES = (
(701,706,'tl_lfs','NovaBus LFS (2007) — Blue Bus'),(901,909,'tl_lfs','NovaBus LFS (2009) — Blue Bus'),
(1201,1217,'tl_xd40','New Flyer XD40 — Blue Bus'),(1601,1614,'tl_xd40','New Flyer XD40 — Blue Bus'),
(2101,2199,'tl_e40','New Flyer E40LFR trolleybus'),(2201,2289,'tl_e40','New Flyer E40LFR trolleybus'),(2501,2574,'tl_e60','New Flyer E60LFR articulated trolleybus'),
(8118,8156,'tl_de60','New Flyer DE60LFR hybrid'),(9401,9499,'tl_lfshev','NovaBus LFS HEV'),(9501,9542,'tl_lfshev','NovaBus LFS HEV'),(9543,9590,'tl_lfs','NovaBus LFS diesel'),(9605,9699,'tl_lfs','NovaBus LFS diesel'),(9701,9725,'tl_lfs','NovaBus LFS diesel'),(9726,9791,'tl_lfs','NovaBus LFS diesel'),(9797,9799,'tl_lfs','NovaBus LFS diesel'),
(14001,14045,'tl_xn40','New Flyer XN40 CNG'),(16001,16051,'tl_xn40','New Flyer XN40 CNG'),(16101,16130,'tl_xd40','New Flyer XD40 diesel'),(16137,16137,'tl_xd40','New Flyer XD40 diesel'),(18101,18206,'tl_xn40','New Flyer XN40 CNG'),(19101,19147,'tl_xn40','New Flyer XN40 CNG'),
(18301,18404,'tl_lfshev','NovaBus LFS HEV'),(18451,18473,'tl_lfssub','NovaBus LFS Suburban'),(23201,23215,'tl_lfse','NovaBus LFSe+'),(24101,24150,'tl_lfscng','NovaBus LFS CNG'),(25101,25184,'tl_lfscng','NovaBus LFS CNG'),(25201,25207,'tl_lfse','NovaBus LFSe+'),(26101,26130,'tl_lfscng','NovaBus LFS CNG'),
*((a,b,'tl_xde60','New Flyer XDE60 hybrid articulated') for a,b in ((12001,12025),(15001,15021),(16201,16226),(18001,18063),(19001,19047),(21001,21025),(22001,22015),(23001,23015),(24001,24016))),
(19401,19432,'tl_enviro','Alexander Dennis Enviro500 MMC'),(21401,21425,'tl_enviro','Alexander Dennis Enviro500 MMC'),
*((a,b,'tl_arboc','ARBOC community shuttle') for a,b in ((19503,19535),(19538,19549),(21501,21562),(24506,24539),(25501,25523))),
*((a,b,'tl_girardin','Girardin G5 community shuttle') for a,b in ((19550,19554),(23601,23606),(23651,23665),(24601,24634),(25601,25627),(26601,26624))),
(27001,27001,'tl_solaris12','Solaris Trollino 12 (provisional)'),(28201,28201,'tl_solaris18','Solaris Trollino 18 (provisional)'),
)
PATTERN=re.compile(r'^(?:BUS\s*#?\s*|FLEET\s*#?\s*|[BHPRSV]\s*)?(\d{3,5})$',re.I)
def identify(label, descriptor_id=None):
    result={'fleet_number':None,'fleet_status':'unavailable','fleet_basis':None,'model_key':'generic','model':None,'model_basis':None}
    for raw,field in ((label,'label'),(descriptor_id,'descriptor ID')):
        if not isinstance(raw,str): continue
        match=PATTERN.fullmatch(raw.strip())
        if not match: continue
        number=match.group(1); n=int(number)
        # Known historical West Vancouver alias; only normalize roster matches.
        if len(number)==5 and number.startswith('80'):
            candidate=int(number[2:]);
            if any(a<=candidate<=b and 'Blue Bus' in name for a,b,k,name in SERIES): n=candidate; number=str(candidate)
        series=next((r for r in SERIES if r[0]<=n<=r[1]),None)
        if not series: continue
        return {**result,'fleet_number':number,'fleet_status':'candidate','fleet_basis':f'TransLink {field}; roster-matched candidate, not verified', 'model_key':series[2], 'model':series[3], 'model_basis':'Preliminary fleet production cohort; individual assignment and feed ID format unverified'}
    if isinstance(label,str):
        match=PATTERN.fullmatch(label.strip())
        if match and int(match.group(1))>=100:
            return {**result,'fleet_number':match.group(1),'fleet_status':'candidate',
                    'fleet_basis':'Numeric display label; physical fleet identity unverified',
                    'model_basis':'No matching production cohort'}
    return result
