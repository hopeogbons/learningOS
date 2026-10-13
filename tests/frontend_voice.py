"""Synthetic frontend acceptance; live provider functionality is not inferred."""
import json,os
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=ROOT/'docs'/'evidence'/'frontend'
EVIDENCE.mkdir(parents=True,exist_ok=True)
base=os.getenv('E2E_BASE_URL','http://127.0.0.1:3000').rstrip('/')
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
 page=browser.new_page(viewport={'width':390,'height':844});errors=[];transcribes=[];synth=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.add_init_script('''
 Object.defineProperty(window,'webkitSpeechRecognition',{value:undefined,configurable:true});
 Object.defineProperty(window,'SpeechRecognition',{value:undefined,configurable:true});
 Object.defineProperty(navigator,'mediaDevices',{value:{getUserMedia:async()=>({getTracks:()=>[{stop:()=>{}}]})},configurable:true});
 class FixtureRecorder { constructor(){this.state='inactive';this.mimeType='audio/webm';} static isTypeSupported(){return true;} start(){this.state='recording';} stop(){this.state='inactive';setTimeout(()=>{this.ondataavailable?.({data:new Blob(['fixture'],{type:'audio/webm'})});this.onstop?.();},10);} }
 window.MediaRecorder=FixtureRecorder;
 window.speechSynthesis.getVoices=()=>[];
 ''')
 def profile(route):
  response=route.fetch();data=response.json();data['ui_locale']='en';route.fulfill(response=response,json=data)
 page.route('**/api/v1/me',profile)
 page.route('**/api/v1/sessions/voice-fixture/next',lambda r:r.fulfill(json={'session_id':'voice-fixture','item_id':'voice-item','version':1,'status':'awaiting_answer','question':'Explain a neutral atom.','teaching':'Atoms contain particles.','citation_ids':[],'voice_turn_count':0}))
 def transcribe(route):
  transcribes.append(route.request.post_data);route.fulfill(json={'text':'A neutral atom has equal numbers of protons and electrons.'})
 def synthesis(route):
  synth.append(route.request.post_data);route.fulfill(status=503,json={'error':{'code':'speech_unavailable','message':'speech unavailable'}})
 page.route('**/api/v1/sessions/voice-fixture/speech/transcribe',transcribe)
 page.route('**/api/v1/sessions/voice-fixture/speech/synthesize',synthesis)
 page.goto(base+'/study?session=voice-fixture&mode=voice')
 page.get_by_role('button',name='Record an answer',exact=True).click()
 page.get_by_role('button',name='Stop recording',exact=True).wait_for()
 page.goto(base+'/collections');page.wait_for_timeout(300)
 assert len(transcribes)==0,'Leaving recording must not submit audio'
 page.goto(base+'/study?session=voice-fixture&mode=voice')
 page.get_by_role('button',name='Record an answer',exact=True).click()
 page.get_by_role('button',name='Stop recording',exact=True).click()
 page.get_by_label('Your answer',exact=True).fill('Editable transcript test')
 page.wait_for_timeout(300)
 assert len(transcribes)==1
 page.get_by_role('button',name='Listen',exact=True).click()
 page.get_by_text('Selected-language speech is unavailable. You can type your answer.',exact=True).wait_for()
 assert len(synth)==1
 data=json.loads(synth[0]);assert data=={'item_id':'voice-item','message_id':'question'}
 assert not errors,errors
 result={'status':'passed','checks':'Mocked recorder cancels on leaving without submit; explicitstop posts owneditem; transcript editable; missing browser voice waits then owned server fallback; unavailable retains typing','live_speech_verified':False,'errors':errors}
 (EVIDENCE/'voice.json').write_text(json.dumps(result,indent=2))
 print(json.dumps(result))
 browser.close()
