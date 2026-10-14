"""Rendered control geometry and collection wording in a synthetic demo only.

Run after starting API/worker/frontend with E2E_BASE_URL. Preserves profile
preferences and deletes only its own generated collection, even on failure.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

import httpx
from playwright.sync_api import expect, sync_playwright

BASE = os.getenv('E2E_BASE_URL', 'http://127.0.0.1:3000').rstrip('/')
ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.getenv('CONTROL_LAYOUT_EVIDENCE', str(ROOT / 'work' / 'control-layout')))

# Measure rendered text, not merely the CSS declarations that implement it.
GEOMETRY = '''el => {
 const rect = el.getBoundingClientRect();
 const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
 const boxes = []; let node;
 while ((node = walker.nextNode())) {
   if (!node.textContent.trim()) continue;
   const range = document.createRange(); range.selectNodeContents(node);
   boxes.push(...range.getClientRects());
 }
 const top = Math.min(...boxes.map(b=>b.top));
 const bottom = Math.max(...boxes.map(b=>b.bottom));
 return {text:el.textContent.trim(), height:rect.height, width:rect.width,
   above:top-rect.top, below:rect.bottom-bottom,
   delta:Math.abs((top+bottom)/2-(rect.top+rect.bottom)/2)};
}'''


def main():
    expect.set_options(timeout=30000)
    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    with httpx.Client(base_url=BASE, timeout=40) as api:
        health = api.get('/api/v1/health'); health.raise_for_status()
        assert health.json()['mode'] == 'demo', 'Synthetic mutations require demo mode'
        profile = api.get('/api/v1/me').json()
        saved = {k: profile[k] for k in ('ui_locale', 'study_locale', 'speech_locale')}
        created = api.post('/api/v1/collections', json={
            'name': 'Control layout ' + uuid.uuid4().hex[:8], 'storage_mode': 'local'})
        created.raise_for_status(); cid = created.json()['id']
        try:
            upload = api.post(f'/api/v1/collections/{cid}/materials',
                files={'file': ('layout.md', b'# Layout fixture\n\n## Control alignment\nConsistent controls keep labels centered and readable.\n', 'text/markdown')},
                headers={'Idempotency-Key': uuid.uuid4().hex})
            upload.raise_for_status()
            deadline = time.monotonic() + 40
            while True:
                job = api.get('/api/v1/jobs/' + upload.json()['job_id']).json()
                if job['state'] == 'succeeded': break
                assert job['state'] not in {'failed', 'needs-attention'}, job
                assert time.monotonic() < deadline, 'Fixture ingestion timeout'
                time.sleep(.2)
            outline = api.get(f'/api/v1/collections/{cid}/outline'); outline.raise_for_status()
            fixture_titles = [chunk['title'] for material in outline.json()['materials'] for chunk in material['chunks']]
            assert len(fixture_titles) == 1 and fixture_titles[0].endswith('Control alignment')
            with sync_playwright() as p:
                executable = os.getenv('PLAYWRIGHT_CHROMIUM_EXECUTABLE', '/usr/bin/chromium')
                options = {'executable_path': executable} if Path(executable).is_file() else {}
                browser = p.chromium.launch(**options, headless=True, args=['--no-sandbox'])
                page = browser.new_page()
                page.set_default_timeout(30000)
                for locale, label in [('en', 'Explore collection'), ('de', 'Sammlung erkunden'), ('ar', 'استكشف المجموعة')]:
                    api.patch('/api/v1/me', json={'ui_locale': locale}).raise_for_status()
                    for width in (390, 1440):
                        page.set_viewport_size({'width': width, 'height': 900})
                        page.goto(BASE + '/collections')
                        expect(page.locator('html')).to_have_attribute('lang', locale)
                        action = page.locator(f'a.btn[href="/collections/{cid}/outline"]')
                        expect(action).to_have_text(label)
                        for button in page.locator('main .btn:visible').all():
                            geometry = button.evaluate(GEOMETRY)
                            assert geometry['height'] >= 43.5, geometry
                            assert geometry['width'] >= 43.5, geometry
                            assert geometry['delta'] <= 2, geometry
                        # Long labels must grow naturally and stay centered, not clip.
                        action.evaluate('el => {el.style.width="110px"; el.dataset.original=el.textContent; el.textContent += " "+el.textContent;}')
                        wrapped = action.evaluate(GEOMETRY)
                        assert wrapped['height'] > 44 and wrapped['delta'] <= 2, wrapped
                        action.evaluate('el => {el.style.width="";el.textContent=el.dataset.original;}')
                        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), (locale,width)
                        page.screenshot(path=str(OUT / f'collections-{locale}-{width}.png'), full_page=True)
                        action.click()
                        expect(page).to_have_url(BASE + f'/collections/{cid}/outline')
                        expect(page.get_by_text(fixture_titles[0], exact=True)).to_be_visible()
                        results.append({'locale': locale, 'width': width, 'centering': 'passed', 'wrapping': 'passed', 'collection_route': 'passed'})
                api.patch('/api/v1/me', json={'ui_locale':'en'}).raise_for_status()
                for width in (360,390,768,991,992,1440):
                    page.set_viewport_size({'width':width,'height':900})
                    page.goto(BASE+'/')
                    expect(page.locator('.quick-tile').first).to_be_visible()
                    page.screenshot(path=str(OUT/f'home-{width}.png'),full_page=True)
                    page.goto(BASE+'/collections')
                    page.get_by_role('button',name='Create Collection',exact=True).click()
                    expect(page.locator('main input.form-control').first).to_be_visible()
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), width
                    for control in page.locator('main input.form-control:visible, main select.form-select:visible').all():
                        box=control.bounding_box(); assert box and box['height'] >= 43.5
                        padding=control.evaluate('el=>{const s=getComputedStyle(el);return [parseFloat(s.paddingTop),parseFloat(s.paddingBottom)]}')
                        assert abs(padding[0]-padding[1]) <= 1, padding
                    page.screenshot(path=str(OUT/f'form-{width}.png'),full_page=True)
                browser.close()
        finally:
            api.patch('/api/v1/me', json=saved).raise_for_status()
            latest = api.get('/api/v1/collections/'+cid); latest.raise_for_status()
            api.delete('/api/v1/collections/'+cid, params={'expected_version':latest.json()['version']}).raise_for_status()
    (OUT/'results.json').write_text(json.dumps({'status':'passed','checks':results},indent=2)+'\n')
    print(json.dumps({'status':'passed','collection_cases':len(results),'form_widths':[360,390,768,991,992,1440],'evidence':str(OUT)}))


if __name__ == '__main__':
    main()
