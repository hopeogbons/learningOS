"""Synthetic connected UI regressions; no Google/provider requests or writes."""
import asyncio,json,os
from pathlib import Path
from collections import Counter
from playwright.async_api import async_playwright,expect
base=os.getenv('E2E_BASE_URL','http://127.0.0.1:3000').rstrip('/')
root=Path(os.getenv('UI_EVIDENCE_DIR',str(Path(__file__).resolve().parents[1]/'.runtime/local-connected-ui')));root.mkdir(parents=True,exist_ok=True)
profile={'id':'synthetic-learner','display_name':'Synthetic Audit','timezone':'Africa/Lagos','ui_locale':'en','study_locale':'en','speech_locale':'en-GB','is_demo':False}
collection={'id':'audit-collection','name':'Synthetic Collection','note':'Synthetic audit only','icon_key':'folder','color_key':'blue','storage_mode':'drive','provisioning_state':'ready','drive_folder_id':'synthetic-folder','material_count':1,'version':1,'position':0,'active_scope':{'id':'scope','chunk_ids':['chunk']},'progress':{'percent':0,'completed_count':0,'total_in_scope':1,'review_needed_count':0}}
dashboard={'learner':profile,'collections_count':0,'due_count':0,'collections':[],'scope_progress':{'percent':0,'completed_count':0,'total_in_scope':0,'review_needed_count':0},'resume':None,'calibration':{},'recent_materials':[],'connections':[],'mode':'live'}
results=[]
async def main():
 async with async_playwright() as p:
  chromium=Path(os.getenv('CHROMIUM_PATH','/usr/bin/chromium'))
  options={'executable_path':str(chromium)} if chromium.is_file() else {}
  browser=await p.chromium.launch(**options,headless=True,args=['--no-sandbox'])
  async def case(name, connected=True, width=1280):
   context=await browser.new_context(viewport={'width':width,'height':900});page=await context.new_page();counts=Counter();posts=[];errors=[]
   page.on('pageerror',lambda e:errors.append(str(e)))
   async def route(r):
    path=r.request.url.split('/api/v1')[-1];counts[path]+=1
    if path=='/me':data=profile
    elif path=='/dashboard':data=dashboard
    elif path=='/connections':data=[{'provider':'drive','status':'connected' if connected else 'disconnected','configured':connected,'setup_state':'ready' if connected else 'demo'}]
    elif path=='/collections' and r.request.method=='POST':
     posts.append(r.request.post_data_json);data=collection
    elif path=='/collections':data={'items':[collection] if 'upload' in name else [],'next_cursor':None,'total':1 if 'upload' in name else 0}
    elif path=='/collections/audit-collection/materials' and r.request.method=='POST':data={'material_id':'synthetic-material','revision_id':'synthetic-revision','job_id':'synthetic-job','status':'queued','storage_state':'upload-pending'}
    elif path=='/collections/audit-collection/materials':data={'items':[],'next_cursor':None,'total':0}
    else:data={}
    await r.fulfill(json=data)
   await page.route('**/api/v1/**',route)
   return context,page,counts,posts,errors
  for connected in [True,False]:
   context,page,counts,posts,errors=await case('collection',connected)
   await page.goto(base+'/collections');await page.get_by_role('button',name='Create Collection',exact=True).click()
   selector=page.locator('select[name=storage_mode]');await expect(selector).to_have_value('drive' if connected else 'local')
   if connected:
    await page.get_by_label('Collection name',exact=True).fill('Synthetic new collection')
    await page.get_by_role('button',name='Save',exact=True).click();await expect(selector).to_have_count(0)
    assert posts[-1]['storage_mode']=='drive',posts
    await page.get_by_role('button',name='Create Collection',exact=True).click();await selector.select_option('local')
    await page.get_by_label('Collection name',exact=True).fill('Explicit local choice');await page.get_by_role('button',name='Save',exact=True).click();await expect(selector).to_have_count(0)
    assert posts[-1]['storage_mode']=='local',posts
   else:assert await selector.locator('option[value=drive]').get_attribute('disabled') is not None
   assert not errors,errors;results.append({'case':'connected-drive-default-explicit-local' if connected else 'offline-local-drive-disabled','status':'passed'});print(results[-1],flush=True)
   await context.close()
  for terminal in ['succeeded','needs-attention','cancelled']:
   context,page,counts,posts,errors=await case('upload-'+terminal,width=390 if terminal=='needs-attention' else 1280)
   phase={'status':terminal}
   async def jobroute(r):
    counts['job']+=1
    await r.fulfill(json={'id':'synthetic-job','status':phase['status'],'result':{'storage_state':'saved-to-drive'} if phase['status']=='succeeded' else {},'error_code':None})
   async def retryroute(r):
    counts['retry']+=1;phase['status']='succeeded';await r.fulfill(json={'id':'synthetic-job','status':'queued'})
   await page.route('**/api/v1/jobs/synthetic-job',jobroute);await page.route('**/api/v1/jobs/synthetic-job/retry',retryroute)
   await page.goto(base+'/add-material?collection=audit-collection');await page.locator('input[type=file]').set_input_files({'name':'synthetic-note.txt','mimeType':'text/plain','buffer':b'Synthetic source for browser fixture.'})
   await page.get_by_role('button',name='Add to Collection',exact=True).click()
   if terminal=='needs-attention':
    await page.get_by_role('button',name='Retry processing',exact=True).click();await page.wait_for_timeout(250);assert counts['retry']==1
   await page.get_by_text('Cancelled' if terminal=='cancelled' else 'Saved to Drive',exact=True).wait_for();await page.wait_for_timeout(500)
   snapshot=counts.copy();await page.wait_for_timeout(3100);assert counts==snapshot,dict(counts-snapshot)
   await page.screenshot(path=str(root/('upload-'+terminal+'.png')),full_page=True)
   assert not errors,errors;results.append({'case':'upload-terminal-stop-receipt-'+terminal,'status':'passed','stable_counts':dict(snapshot)});print(results[-1],flush=True)
   await context.close()
  for status in ['finished','awaiting_answer','needs_attention']:
   context,page,counts,posts,errors=await case('study-'+status,width=390 if status=='awaiting_answer' else 1280)
   async def nextfixture(r):
    counts['next']+=1
    await r.fulfill(json={'session_id':'audit-session','item_id':'audit-item','version':1,'status':status,'teaching':'Synthetic teaching.','question':'Synthetic question?','citation_ids':[],'voice_turn_count':0})
   await page.route('**/api/v1/sessions/audit-session/next',nextfixture)
   await page.route('**/api/v1/sessions/audit-session/summary',lambda r:r.fulfill(json={'completed_titles':[],'remaining_titles':[],'sample_count':0}))
   await page.goto(base+'/study?session=audit-session');await page.wait_for_timeout(650)
   initial=counts['next'];assert initial==1,counts
   await page.wait_for_timeout(2800);assert counts['next']==1,counts
   await page.screenshot(path=str(root/('study-'+status+'.png')),full_page=True)
   assert not errors,errors;results.append({'case':'study-stop-'+status,'status':'passed','next_requests':counts['next']});print(results[-1],flush=True);await context.close()
  context,page,counts,posts,errors=await case('study-slow')
  concurrent=0;maximum=0
  async def slow(r):
   nonlocal concurrent,maximum
   counts['next']+=1;concurrent+=1;maximum=max(maximum,concurrent)
   await asyncio.sleep(2.2);concurrent-=1
   await r.fulfill(json={'session_id':'audit-session','item_id':'audit-item','version':1,'status':'generating' if counts['next']==1 else 'awaiting_answer','teaching':'Synthetic teaching.','question':'Synthetic question?','citation_ids':[]})
  await page.route('**/api/v1/sessions/audit-session/next',slow)
  await page.goto(base+'/study?session=audit-session');await page.get_by_label('Your answer',exact=True).wait_for();await page.wait_for_timeout(2800)
  assert maximum==1 and counts['next']==2,(maximum,counts)
  assert not errors,errors;results.append({'case':'study-slow-pending-no-overlap-stops-ready','status':'passed','max_concurrent':maximum,'next_requests':counts['next']});print(results[-1],flush=True);await context.close()
  await browser.close()
 report={'status':'passed','checks':results,'all_sources_synthetic':True,'live_provider_calls':0,'Google_consent_proven':False}
 (root/'results.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
if __name__=='__main__':
 asyncio.run(main())
