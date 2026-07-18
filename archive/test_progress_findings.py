"""
Findings from challenge flow investigation (updated Jul 14, 2026)

## OVERALL STATUS
The Roblox proof-of-work challenge flow WORKS end-to-end in the browser,
with two blockers: (1) PX anti-bot behavioral delay, (2) Captcha response
from /challenge/v1/continue that prevents login retry.

## KEY BREAKTHROUGH: Mouse interaction eliminates PX delay
The ~50-second delay between onFormSubmit() and the login POST was caused
by PX waiting for behavioral signals (mouse movements, focus events). By
injecting simulated mouse events before form submission, the delay drops
to 1-15 seconds.

### Required mouse interaction (test_humanlike.py, test_expect.py):
1. 20+ mousemove events on the page
2. Focus the username input field (dispatch focus event)
3. Fill username (page.fill)
4. Fill password (page.fill)
5. 10+ more mousemove events
6. Wait 1+ second between actions

### If mouse interaction is NOT provided (test_timing.py, test_alldelays.py):
- ~50 second delay between onFormSubmit() and login POST
- NO network activity during the delay period
- The delay is reproducible across multiple browser sessions

## FULL FLOW TIMELINE (with mouse interaction)
t=0s: onFormSubmit() called
t=1-15s: POST /v2/login → 403 (rblx-challenge-id, rblx-challenge-type)
t=2-16s: GET pow-puzzle?sessionID=<UUID> → 200 {artifacts: {N, A, T}}
t=2-16s: GET worker-resources?component=ChallengeWebWorkers
t=4-18s: POST pow-puzzle/<sessionID>/verify → {answerCorrect: true, redemptionToken}
t=4-18s: POST /challenge/v1/continue → 200 {challengeType: "captcha", ...}
(NEVER): Login retry (POST /v2/login with challenge headers)

## /challenge/v1/continue RESPONSE (for test credentials)
```json
{
  "challengeId": "us-central-...",
  "challengeType": "captcha",
  "challengeMetadata": "{\"captchaToken\":\"\", \"unifiedCaptchaId\":\"...\", \"dataExchangeBlob\":\"...\"}"
}
```
challengeType = "captcha" → login is BLOCKED until captcha solved
For real/low-risk accounts, this might return a different result (proceed without captcha).

## WEBWORKER BEHAVIOR
- CSP bypass (bypass_csp=True) IS required for Worker blob URL to load
- Worker computes the POW in ~2-3 seconds (T=400000 iterations)
- When __cf_bm cookie is present, Worker creation fails (net::ERR_FAILED)
- When __cf_bm is absent, Worker works correctly
- The __cf_bm cookie is intermittent (Cloudflare Bot Management)

## WHAT DOESN'T WORK
1. httpx fetching puzzle API: All httpx requests to apis.roblox.com
   return 404 "session not found or inactive" (Cloudflare blocks non-browser clients)
2. page.evaluate(fetch(...)) for login: PX doesn't intercept fetch calls
   from page.evaluate context (no challenge headers in response)
3. page.route intercept of login: Bypasses PX entirely, challenge flow never starts
4. Any manual retry with redemption token: Always returns 403
5. Login retry after challenge: PX never retries after /challenge/v1/continue

## STILL UNKNOWN
1. Does /challenge/v1/continue skip captcha for real credentials?
2. If captcha is solved, does PX proceed and retry login?
3. Why does __cf_bm block the WebWorker (is it really Cloudflare or PX?)

## KEY FILES
- test_expect.py: Captures full flow including puzzle and /challenge/v1/continue responses
- test_humanlike.py: First successful test with mouse interaction (shows ~5s timeline)
- test_reproduce.py: Reproduces the flow with proper timing
- test_fullflow.py: Attempted response body capture (buffering issue)
- test_cdp_bypass5.py: CDP bypass with httpx puzzle (404 confirmation)
"""
