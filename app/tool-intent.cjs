// Deterministic clarification for explicitly selected tools with no usable target.
function missingTarget(prompt, requested, messages) {
  const targeted = requested.find(name => ['browser_inspect', 'browser_open', 'http_request', 'website_assess'].includes(name));
  if (!targeted) return null;
  const text = prompt.replace(/@[a-zA-Z][a-zA-Z0-9_]*/g, '').trim();
  const hasURL = /https?:\/\/[^\s<>]+|\b(?:[a-z0-9-]+\.)+[a-z]{2,}(?:[/:?]|\b)/i.test(text);
  const prior = messages.some(m => ['user', 'tool'].includes(m.role) && !/^(Error:|User declined)/.test(m.content || '') && /https?:\/\//i.test(m.content || ''));
  // A named topic can be discovered through search. Bare deictic requests cannot.
  const generic = /^(?:(?:please|use|open|inspect|browse|read|fetch|check|assess|look|at|this|that|it|page|website|site|link|url|address|for|me|the|now|and|do|a|an|with)\b[\s,.!?]*)*$/i.test(text);
  if (!hasURL && !prior && generic) return targeted === 'http_request' ? 'Which URL should I request?' : 'Which website URL should I inspect?';
  return null;
}
function browserCloseRequested(prompt, requested = []) {
 if (/\b(?:do not|don't|never)\s+close\b|\bkeep\b[^.!?]*\b(?:browser|session)\b[^.!?]*\bopen\b/i.test(prompt)) return false;
 if (/\b(?:explain|what|how)\b/i.test(prompt) && !/\b(?:and|then)\s+close\b/i.test(prompt)) return false;
 return requested.includes('browser_close') || /\bclose\s+(?:(?:the|this|that|my|your|a)\s+)?(?:browser(?:\s+session)?|session)\b|\bbrowser_close\s+(?:when|after)\b/i.test(prompt);
}
module.exports = { missingTarget, browserCloseRequested };
