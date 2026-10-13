"""Synthetic frontend acceptance; live provider functionality is not inferred."""
import json,os
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=ROOT/'docs'/'evidence'/'frontend'
EVIDENCE.mkdir(parents=True,exist_ok=True)
base=os.getenv('E2E_BASE_URL','http://127.0.0.1:3000').rstrip('/');results=[]
axe=os.environ['AXE_SCRIPT_PATH']
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
 for width in [390,1440]:
  page=browser.new_page(viewport={'width':width,'height':1000})
  def profile(route):
   response=route.fetch();data=response.json();data['ui_locale']='en';route.fulfill(response=response,json=data)
  page.route('**/api/v1/me',profile)
  for route in ['/','/collections','/outline','/add-material','/study','/review','/progress','/connections','/profile','/search','/notifications']:
   response=page.goto(base+route,wait_until='networkidle');assert response.status==200, f'{route}: HTTP {response.status}';page.wait_for_timeout(500);page.add_script_tag(path=axe)
   result=page.evaluate('async()=>{const r=await axe.run(document,{runOnly:{type:"tag",values:["wcag2a","wcag2aa","wcag21aa"]}});return {violations:r.violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))})),passes:r.passes.length};}')
   results.append({'route':route,'width':width,**result})
  page.close()
 browser.close()
(EVIDENCE/'a11y-routes.json').write_text(json.dumps(results,indent=2))
result={'routes':len(results),'violations':sum(len(r['violations']) for r in results),'failed':[{k:v for k,v in r.items() if k!='passes'} for r in results if r['violations']]}
(EVIDENCE/'a11y.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result))

assert result['violations']==0, 'Review axe violations before claiming accessibility gate passed'
