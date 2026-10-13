#!/usr/bin/env python3
"""L01 catalog/ICU, locale registry and locally bundled glyph coverage checks.

Does not certify L02 browser layout, native-language L03 semantic grading, or L04 speech.
Run from any working directory. --report emits synthetic-only verification metadata.
"""
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
CATALOGS = FRONTEND / "src/i18n/catalogs"
ORDER = ["en", "zh-Hans", "es", "ar", "pt", "fr", "ja", "ru", "de", "id"]
all_catalogs = {locale: json.loads((CATALOGS / f"{locale}.json").read_text()) for locale in ORDER}
errors = []
base = all_catalogs["en"]
inventory = set(re.findall(r"^\s*['\"]([^'\"]+)['\"]\s*:\s*['\"]", (FRONTEND / "src/lib/messages.ts").read_text(), re.MULTILINE))
if set(inventory) != set(base):
    errors.append(f"English inventory/catalog mismatch: {set(inventory) ^ set(base)}")
for locale, catalog in all_catalogs.items():
    if set(catalog) != set(base):
        errors.append(f"{locale}: missing/extra keys {set(catalog) ^ set(base)}")
    for key, value in catalog.items():
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{locale}:{key}: empty/non-text translation")
        if re.search(r"[\u202a-\u202e\u2066-\u2069]", value):
            errors.append(f"{locale}:{key}: unexpected embedded bidi control (use HTML bdi)")
        if re.search(r"\bTODO\b|\bTRANSLATE\b|\[missing", value):
            errors.append(f"{locale}:{key}: untranslated marker")
# Literal usages must resolve. Dynamic family keys are checked by normal app tests.
for path in (FRONTEND / "src").rglob("*.tsx"):
    if "i18n" in path.parts:
        continue
    for key in re.findall(r"\bt\(\s*['\"]([^'\"]+)['\"]", path.read_text()):
        if key not in base:
            errors.append(f"{path.relative_to(ROOT)}: unknown literal key {key}")
registry = json.loads((ROOT / "contracts/language-registry.json").read_text())["languages"]
if [entry["ui_locale"] for entry in registry] != ORDER:
    errors.append("Registry language order differs from the screenshot")
registry_source = (FRONTEND / "src/i18n/registry.ts").read_text()
for entry in registry:
    for field in ["ui_locale", "native_label", "default_speech_locale"]:
        if json.dumps(entry[field], ensure_ascii=False) not in registry_source:
            errors.append(f"Registry implementation lacks {entry[field]}")
# Verify local CSS references, WOFF2 magic and license provenance.
font_css = (FRONTEND / "src/i18n/fonts.css").read_text()
font_paths = re.findall(r"url\((/fonts/[^)]+)\)", font_css)
for url in font_paths:
    asset = FRONTEND / "public" / url.lstrip("/")
    if not asset.exists() or asset.read_bytes()[:4] != b"wOF2":
        errors.append(f"Missing/invalid local font {url}")
provenance = json.loads((FRONTEND / "public/fonts/PROVENANCE.json").read_text())
if len(provenance) != 3 or any(font["license"] != "OFL-1.1" for font in provenance):
    errors.append("Font provenance/license missing")
for package in ["noto-sans-arabic", "noto-sans-sc", "noto-sans-jp"]:
    if not (FRONTEND / f"public/fonts/{package}-LICENSE.txt").exists():
        errors.append(f"Missing license for {package}")

# Exercise the installed supported ICU formatter and AST parser, not a home-grown regex formatter.
js = r'''
const fs=require('fs'),path=require('path');
const {IntlMessageFormat}=require('intl-messageformat');
const {parse}=require('@formatjs/icu-messageformat-parser');
const root=path.join(process.cwd(),'src/i18n/catalogs');
const locales=['en','zh-Hans','es','ar','pt','fr','ja','ru','de','id'];
const base=JSON.parse(fs.readFileSync(path.join(root,'en.json'),'utf8'));
const variables=(ast)=>{let result=new Set();for(const item of ast){
 if(item.type>=1&&item.type<=6)result.add(item.value);
 if(item.options)for(const option of Object.values(item.options))for(const variable of variables(option.value))result.add(variable);
 if(item.children)for(const variable of variables(item.children))result.add(variable);
}return [...result].sort();};
const expected=Object.fromEntries(Object.entries(base).map(([key,text])=>[key,variables(parse(text))]));
let checks=0;const errors=[];const pluralExamples={};
for(const locale of locales){const catalog=JSON.parse(fs.readFileSync(path.join(root,locale+'.json'),'utf8'));
 for(const [key,text] of Object.entries(catalog)){
 try {const ast=parse(text); const names=variables(ast);if(JSON.stringify(names)!==JSON.stringify(expected[key]))throw Error('interpolation variables differ');
  const format=new IntlMessageFormat(ast,locale);
  for(const count of [0,1,2,3,5,11,21,101,1.5]){
   const result=format.format({count,done:1,total:3,revision:7});
   if(typeof result!=='string'||!result.trim()||result.includes('{count'))throw Error('unresolved output');checks++;
  }
 }catch(error){errors.push(locale+':'+key+': '+error.message);}
 }
 pluralExamples[locale]=[0,1,2,3,11,21].map(count=>new IntlMessageFormat(catalog['common.materialCount'],locale).format({count}));
}
const pseudoLong=Object.fromEntries(Object.entries(base).map(([k,v])=>[k,'⟦ '+v.replace(/[A-Za-z]+/g,s=>s+' '+s+' '+s)+' ⟧']));
if(pseudoLong['nav.addMaterial'].length < base['nav.addMaterial'].length*2)errors.push('Pseudo-long fixture too short');
console.log(JSON.stringify({checks,errors,pluralExamples,pseudoLongFixture:{'nav.addMaterial':pseudoLong['nav.addMaterial'],'profile.preferences':pseudoLong['profile.preferences']}}));
if(errors.length)process.exitCode=1;
'''
result = subprocess.run(["node", "-e", js], cwd=FRONTEND, capture_output=True, text=True)
try:
    runtime = json.loads(result.stdout)
except json.JSONDecodeError:
    runtime = {"errors": [result.stderr or result.stdout or "Node formatter check failed"]}
errors.extend(runtime.get("errors", []))
if result.returncode and not runtime.get("errors"):
    errors.append(result.stderr)
# Confirm bundled CSS subsets cover every native script character used in these catalogs.
# This checks coverage metadata; real glyph rendering remains a browser gate.
for locale, family, native_pattern in [
    ("ar", "Noto Sans Arabic", r"[\u0600-\u06ff]"),
    ("zh-Hans", "Noto Sans SC", r"[\u4e00-\u9fff]"),
    ("ja", "Noto Sans JP", r"[\u3040-\u30ff\u4e00-\u9fff]"),
]:
    intervals = []
    for block in re.findall(r"@font-face\s*\{([^}]+)\}", font_css):
        if f"font-family: '{family}'" not in block:
            continue
        match = re.search(r"unicode-range:\s*([^;]+)", block)
        for code_range in match.group(1).split(",") if match else []:
            ends = code_range.strip().removeprefix("U+").split("-")
            intervals.append((int(ends[0], 16), int(ends[-1], 16)))
    characters = set("".join(all_catalogs[locale].values()))
    for character in characters:
        if re.match(native_pattern, character) and not any(start <= ord(character) <= end for start, end in intervals):
            errors.append(f"{locale}: bundled font unicode ranges lack {character} U+{ord(character):04X}")
# UTF-8 Arabic and CJK must remain real text, not transliterations.
for locale, pattern in [("ar", r"[\u0600-\u06ff]"), ("zh-Hans", r"[\u4e00-\u9fff]"), ("ja", r"[\u3040-\u30ff\u4e00-\u9fff]")]:
    for key in ["nav.home", "nav.collections", "profile.original", "study.voiceUnavailable"]:
        if not re.search(pattern, all_catalogs[locale][key]):
            errors.append(f"{locale}:{key}: expected native-script text missing")
report = {"check": "L01 catalog/ICU and local asset checks", "status": "passed" if not errors else "failed", "locales": ORDER, "keys_per_locale": len(base), "runtime_formats_exercised": runtime.get("checks", 0), "font_assets": len(font_paths), "plural_examples": runtime.get("pluralExamples"), "pseudo_long_fixture": runtime.get("pseudoLongFixture"), "errors": errors, "limitations": ["Translations are authored candidates; proficient/native linguistic approval is outstanding.", "Catalog and asset checks do not establish RTL/mobile/zoom browser layout, live generated study-language quality, or STT/TTS support.", "Synthetic long-label fixture requires browser injection/review; generating it alone is not a layout pass."]}
if "--report" in sys.argv:
    print(json.dumps(report, ensure_ascii=False, indent=2))
else:
    print(f"{report['status']}: {len(ORDER)} locales, {len(base)} keys each, {report['runtime_formats_exercised']} ICU formats, {len(font_paths)} local font assets")
    for error in errors:
        print(error)
sys.exit(bool(errors))
