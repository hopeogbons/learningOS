"""Synthetic consent-error UI regressions; real Google requests are intercepted."""
import json,os
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
ROOT=Path(os.getenv('UI_EVIDENCE_DIR',str(Path(__file__).resolve().parents[1]/'.runtime/local-connected-ui')));ROOT.mkdir(parents=True,exist_ok=True)
base=os.getenv('E2E_BASE_URL','http://127.0.0.1:3000').rstrip('/');results=[]
with sync_playwright() as p:
 chromium=Path(os.getenv('CHROMIUM_PATH','/usr/bin/chromium'))
 options={'executable_path':str(chromium)} if chromium.is_file() else {}
 browser=p.chromium.launch(**options,headless=True,args=['--no-sandbox'])
 for width in (390,1440):
  context=browser.new_context(viewport={'width':width,'height':1000})
  context.add_cookies([{'name':'learningos_csrf','value':'synthetic-csrf','url':base}]);page=context.new_page();errors=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  profile={'id':'synthetic-learner','display_name':'Synthetic Audit','timezone':'Africa/Lagos','ui_locale':'en','study_locale':'en','speech_locale':'en-GB','is_demo':False}
  page.route('**/api/v1/dashboard',lambda r:r.fulfill(json={'learner':profile,'collections_count':0,'due_count':0,'collections':[],'scope_progress':{'percent':0,'completed_count':0,'total_in_scope':0,'review_needed_count':0},'resume':None,'calibration':{},'recent_materials':[],'connections':[],'mode':'live'}))
  page.route('**/api/v1/connections',lambda r:r.fulfill(json=[{'provider':'drive','status':'disconnected','configured':True,'setup_state':'ready'}]))
  page.route('**/api/v1/me',lambda r:r.fulfill(json={'display_name':'Synthetic Audit','ui_locale':'en','timezone':'Africa/Lagos'}))
  for code,message in [('oauth_denied','consent was declined'),('drive_scope_incomplete','all required Drive permissions'),('oauth_network','could not finish connecting'),('unrecognized_private_token',None)]:
   page.goto(base+'/connections?drive_error='+code,wait_until='networkidle')
   expect(page.get_by_role('button',name='Connect',exact=True)).to_be_enabled()
   if message:expect(page.get_by_role('alert').filter(has_text=message)).to_be_visible()
   else:assert 'unrecognized_private_token' not in page.inner_text('body')
   assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
   if code=='oauth_denied':page.screenshot(path=str(ROOT/f'consent-denied-{width}.png'),full_page=True)
   results.append({'viewport':width,'callback_code':code,'outcome':'passed','connect_enabled':True})
  calls=[]
  def connect(route):
   calls.append({'method':route.request.method,'csrf':route.request.headers.get('x-csrf-token')=='synthetic-csrf'})
   route.fulfill(json={'authorization_url':'https://accounts.google.com/o/oauth2/v2/auth?state=synthetic'})
  page.route('**/api/v1/connections/drive/connect',connect)
  page.route('https://accounts.google.com/**',lambda r:r.fulfill(body='Synthetic intercepted consent'))
  page.goto(base+'/connections?drive_error=oauth_denied',wait_until='networkidle')
  page.get_by_role('button',name='Retry',exact=True).click();page.wait_for_url('https://accounts.google.com/**')
  assert calls==[{'method':'POST','csrf':True}]
  results.append({'viewport':width,'case':'consent_retry_restarts_oauth_POST','outcome':'passed','real_google':'intercepted'})
  calls.clear();page.goto(base+'/connections',wait_until='networkidle')
  page.get_by_role('button',name='Connect',exact=True).click();page.wait_for_url('https://accounts.google.com/**')
  assert calls==[{'method':'POST','csrf':True}];assert not errors,errors
  results.append({'viewport':width,'case':'configured_connect_still_enabled_POST_CSRF','outcome':'passed','real_google':'intercepted'})
  page.unroute('**/api/v1/connections')
  page.route('**/api/v1/connections',lambda r:r.fulfill(json=[{'provider':'drive','status':'connected','configured':True,'setup_state':'ready'}]))
  page.route('**/api/v1/collections',lambda r:r.fulfill(json={'items':[{'id':'ready-folder','storage_mode':'drive','provisioning_state':'ready'},{'id':'failed-folder','storage_mode':'drive','provisioning_state':'needs-attention'}],'next_cursor':None,'total':2}))
  sync_actions=[]
  def sync_action(route):
   sync_actions.append(route.request.url.split('/api/v1')[-1]);route.fulfill(json={'job_id':'synthetic-job','status':'queued'})
  page.route('**/api/v1/collections/*/sync',sync_action)
  page.route('**/api/v1/collections/*/drive-folder/provision',sync_action)
  page.goto(base+'/connections',wait_until='networkidle')
  page.get_by_role('button',name='Sync now',exact=True).click()
  expect(page.get_by_role('status').filter(has_text='Sync')).to_be_visible()
  assert sync_actions==['/collections/ready-folder/sync','/collections/failed-folder/drive-folder/provision'],sync_actions
  results.append({'viewport':width,'case':'sync_retries_failed_folder_and_scans_ready_folder','outcome':'passed'})
  context.close()
 browser.close()
(ROOT/'consent-results.json').write_text(json.dumps({'cases':results,'passed':len(results),'synthetic_only':True},indent=2)+'\n')
print('Passed '+str(len(results))+' consent UI checks')
