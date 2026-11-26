"""Optional offline UI smoke test: pip install playwright; playwright install chromium.
No live feed, Leaflet or tile requests. Run python tests/mobile_browser_check.py.
"""
from playwright.sync_api import sync_playwright
import time
now=int(time.time())
vehicles=[dict(id=f'b{i}',lat=48.45+i*.001,lon=-123.45,route=str(4+i),headsign='Downtown via Douglas Street',fleet_number=str(9400+i),model_key='nova3',model='NovaBus LFS Gen 3',nova_generation=3,timestamp=now,trip_id=f't{i}') for i in range(22)]
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=__import__('shutil').which('chromium'),args=['--no-sandbox'])
 for w,h,theme,apple in [(320,568,"dark",False),(390,844,"dark",True),(844,390,"dark",True),(956,440,"dark",True),(360,740,"classic",False),(820,1180,"dark",True),(1024,768,"dark",True),(1180,820,"dark",True),(1366,768,"dark",False)]:
  phone_layout=w<1000
  touch=phone_layout or apple
  ctx=browser.new_context(viewport={'width':w,'height':h},is_mobile=touch,has_touch=touch,device_scale_factor=1,service_workers='block')
  ctx.add_init_script("localStorage.setItem('bct_theme','dark');")
  page=ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  from pathlib import Path
  import re,json
  root=Path(__file__).resolve().parents[1]/'web'
  html=(root/'index.html').read_text()
  html=re.sub(r'<link[^>]+href="/([^"?]+\.css)(?:\?[^" ]*)?"[^>]*>',lambda m:'<style>'+ (root/m[1]).read_text()+'</style>',html)
  html=re.sub(r'<link[^>]+https?://[^>]+>','',html)
  html=re.sub(r'<script[^>]+src="https?://[^>]+></script>','',html)
  html=re.sub(r'<script[^>]+src="/([^"?]+\.js)(?:\?[^" ]*)?"[^>]*></script>',lambda m:'<script>'+ (root/m[1]).read_text().replace('</script>','<\\/script>')+'</script>',html)
  data={'system':'victoria','vehicles':vehicles,'count':len(vehicles),'fetched_at':now,'source_timestamp':now,'metadata_ready':True,'revision':1}
  html=html.replace('<head>','<head><script>Object.defineProperty(window,"localStorage",{value:{getItem:k=>k==="bct_theme"?' + json.dumps(theme) + ':null,setItem:()=>{}}});window.fetch=async(u)=>({ok:true,json:async()=>String(u).includes("/api/vehicles")?'+json.dumps(data)+':{}});</script>')
  if apple:
   ua='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15) AppleWebKit/605.1.15 Safari/605.1.15' if w>=800 and h>500 else 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1'
   html=html.replace('<head>','<head><script>Object.defineProperty(navigator,"userAgent",{value:'+json.dumps(ua)+'});Object.defineProperty(navigator,"platform",{value:"MacIntel"});Object.defineProperty(navigator,"maxTouchPoints",{value:5});</script>')
  # Move deferred scripts to the end, preserving execution order.
  scripts=re.findall(r'<script>([\s\S]*?)</script>',html)
  html=re.sub(r'<script>[\s\S]*?</script>','',html).replace('</body>',''.join('<script>'+x+'</script>' for x in scripts)+'</body>')
  page.set_content(html,wait_until='domcontentloaded');page.wait_for_timeout(400)
  if phone_layout:
   assert page.locator('#mobileOpen').is_visible(),(w,'routes missing',errors)
   top=page.locator('.top-bar').bounding_box();settings=page.locator('#settingsOpen').bounding_box();assert settings['x']+settings['width']<=w+1,(w,settings)
   nav=page.locator('.mobile-actions').bounding_box();assert nav['y']+nav['height']<=h,(w,nav)
   page.locator('#mobileDepartures').click();assert page.locator('#nearbyBoard').evaluate('(e)=>e.open');page.locator('#mobileDepartures').click();assert not page.locator('#nearbyBoard').evaluate('(e)=>e.open')
   page.locator('#mobileOpen').click();page.wait_for_timeout(100);sheet=page.locator('#sidebar').bounding_box();mapbox=page.locator('#map').bounding_box();assert abs(mapbox['height']-sheet['y'])<=2,(w,sheet,mapbox)
   assert page.locator('#sidebar').evaluate('(e)=>e.scrollHeight>e.clientHeight'),(w,'not scrollable')
   page.locator('#sheetHandle').click();assert page.locator('body').evaluate("e=>e.classList.contains('sheet-full')")
   page.locator('#sheetHandle').press('Enter');assert not page.locator('body').evaluate("e=>e.classList.contains('sheet-full')")
   page.locator('#routeSearch').fill('14');page.locator('#routeSearch').press('Enter');page.wait_for_timeout(100)
   page.locator('#expandAll').count()
   # Select a route then a bus via the actual list.
   page.locator('.route-group-heading').first.click();page.locator('.bus-item').first.click();page.wait_for_timeout(150)
   assert page.locator('#detailSection').is_visible(),(w,errors)
   page.locator('#sidebarClose').click();assert page.locator('#mobileOpenText').inner_text()=='Bus details'
   page.locator('#mobileOpen').click();assert page.locator('#detailSection').is_visible()
   page.locator('#detailSection .back-button').click();assert page.locator('#routeSearch').is_visible()
   page.locator('#sidebarClose').click();page.locator('#settingsOpen').click();assert page.locator('#v34Settings').evaluate('(e)=>e.open');page.locator('#settingsClose').click()
   assert page.locator('html').evaluate('e=>e.scrollWidth<=innerWidth+1'),w
  else:
   assert not page.locator('#mobileOpen').is_visible();assert page.locator('#menuToggle').is_visible();assert page.locator('#sidebar').bounding_box()['width']<400
  if apple:
   assert page.locator('html').evaluate("e=>e.classList.contains('apple-touch')")
   page.locator('#settingsOpen').click();page.locator('#installHelpButton').click()
   assert page.locator('#installHelp').is_visible()
   assert 'Open as Web App' in page.locator('#installHelp').inner_text()
   page.locator('#installHelpClose').click()
   assert not page.locator('#installHelp').is_visible()
  assert not errors, errors
  print(w,h,'PASS',flush=True);ctx.close()
 browser.close()
