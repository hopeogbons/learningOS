"""Synthetic frontend acceptance; live provider functionality is not inferred."""
import json,time,uuid,os
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=ROOT/'docs'/'evidence'/'frontend'
EVIDENCE.mkdir(parents=True,exist_ok=True)
base=os.getenv('E2E_BASE_URL','http://127.0.0.1:3000').rstrip('/')
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
 context=browser.new_context(viewport={'width':390,'height':844})
 page=context.new_page();errors=[]
 page.on('pageerror',lambda error: errors.append(str(error)))
 def owned_profile(route):
  if route.request.method=='GET':
   response=route.fetch();data=response.json();data['ui_locale']='en';route.fulfill(response=response,json=data)
  else:route.continue_()
 page.route('**/api/v1/me',owned_profile)
 page.goto(base+'/collections');page.get_by_role('button',name='Create Collection',exact=True).click()
 name='Frontend UI '+uuid.uuid4().hex[:8]
 page.get_by_label('Collection name',exact=True).fill(name)
 page.get_by_role('button',name='Save',exact=True).click()
 page.get_by_role('link',name=name,exact=True).wait_for()
 href=page.get_by_role('link',name=name,exact=True).get_attribute('href');cid=href.split('/')[2]
 page.goto(base+'/add-material?collection='+cid)
 page.locator('input[type=file]').set_input_files({'name':'ui-material.md','mimeType':'text/markdown','buffer':b'# UI fixture\n\n## Atomic number\nThe atomic number equals the number of protons in an atom.\n\n## Neutral atoms\nA neutral atom has equal numbers of protons and electrons.\n'})
 page.get_by_role('button',name='Add to Collection',exact=True).click()
 page.get_by_role('status').filter(has_text='Material received').wait_for()
 deadline=time.monotonic()+25
 while time.monotonic()<deadline:
  outline=context.request.get(base+'/api/v1/collections/'+cid+'/outline').json()
  if any(m['chunks'] for m in outline['materials']):break
  time.sleep(.2)
 assert len(outline['materials'][0]['chunks'])==2
 page.goto(base+href);page.get_by_label('Atomic number',exact=True).check()
 page.locator('.scope-toolbar').get_by_text('1 title selected',exact=True).wait_for()
 page.get_by_role('button',name='Move down: Atomic number',exact=True).click()
 page.get_by_role('button',name='Save order',exact=True).click()
 deadline=time.monotonic()+10
 while time.monotonic()<deadline:
  saved=context.request.get(base+'/api/v1/collections/'+cid+'/outline').json()
  if saved['materials'][0]['chunks'][0]['title']=='Neutral atoms':break
  time.sleep(.2)
 assert saved['materials'][0]['chunks'][0]['title']=='Neutral atoms'
 page.get_by_role('button',name='Go — save scope and study',exact=True).click()
 page.wait_for_url('**/study?collection=**')
 fresh=context.request.get(base+'/api/v1/collections/'+cid).json();assert fresh['progress']['total_in_scope']==1
 page.get_by_role('button',name='Open menu',exact=True).click()
 dialog=page.get_by_role('dialog');dialog.wait_for();page.keyboard.press('Shift+Tab')
 assert page.evaluate('document.querySelector("[role=dialog]").contains(document.activeElement)')
 page.keyboard.press('Escape');page.wait_for_timeout(100);assert page.get_by_role('button',name='Open menu',exact=True).evaluate('(el)=>el===document.activeElement')
 page.screenshot(path=str(EVIDENCE/'study-mobile.png'),full_page=True)
 assert not errors,errors
 result={'checks':'UI create, actual file upload, worker extraction, title select, keyboard move/order persistence, scope Go, drawer focus and restore','status':'passed','collection_id':cid,'pageerrors':errors}
 (EVIDENCE/'journeys.json').write_text(json.dumps(result,indent=2))
 print(json.dumps(result))
 browser.close()
