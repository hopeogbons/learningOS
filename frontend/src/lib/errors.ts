/** Backend diagnostic codes stay server-side; users receive catalog-owned guidance. */
export function friendlyErrorKey(error: string): string {
  const text = error.toLowerCase();
  if (/conflict|changed|version/.test(text)) return "outline.conflict";
  if (/speech|audio|microphone/.test(text)) return "study.voiceUnavailable";
  if (/drive|oauth|provider|credential|unconfigured/.test(text))
    return "connections.credentials";
  if (/photo|image|vision|blurry|unreadable|ocr/.test(text))
    return "upload.photoHelp";
  if (
    /url|link|ssrf|public|caption|http|youtube|gated|network_blocked/.test(text)
  )
    return "upload.linkHelp";
  if (
    /oversize|unsupported_type|encrypted|empty_source|mime|file|size/.test(text)
  )
    return "upload.accepted";
  if (/locale|model_unavailable|provider_unavailable|demo_fixture/.test(text))
    return "common.notAvailable";
  if (/scope|select at least|chunk/.test(text)) return "study.chooseScope";
  if (/confidence/.test(text)) return "study.selectConfidence";
  return "common.error";
}
