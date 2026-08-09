# budgetify.app

The public website for **Budgetify** — the answer pages, the FAQ, the Privacy
Policy, and the data-deletion instructions.

Split out of the app repository
([Yolo-cell-hash/budgetify](https://github.com/Yolo-cell-hash/budgetify)),
where it used to live in `docs/` and was served by GitHub Pages. The app's
source stays there; this repo is only the site.

## What's here

```
index.html                    landing page
offline-expense-tracker/      answer page — what "offline" really means
no-internet-permission/       answer page — the permission claim, and how to verify it
sms-expense-tracker/          answer page — on-device SMS/UPI parsing
faq/                          FAQ
privacy-policy/               Privacy Policy  ← the URL registered with Google Play
data-deletion/                how to erase your data
assets/                       stylesheet, app icon, Manrope font files
robots.txt                    crawl rules — AI crawlers explicitly allowed
sitemap.xml                   hand-maintained; add new pages here too
llms.txt                      condensed summary for AI assistants
tools/ai_visibility.py        measures whether AI assistants name Budgetify
vercel.json                   trailing-slash + cache/security headers
.vercelignore                 keeps tools/ and README out of the deployment
```

Plain static HTML and CSS. No build step, no framework, no dependencies —
every path is relative, so it works the same served from a subdirectory or
from the domain root. Fonts are self-hosted (see `assets/fonts/OFL.txt`);
nothing is fetched from a third party, which keeps the site as free of
tracking as the app it describes.

## The answer pages

The three pages under `offline-expense-tracker/`, `no-internet-permission/`
and `sms-expense-tracker/` exist for discovery, not decoration.

Budgetify's Play Store listing ranked for its own name and nothing else, and a
web search for "Budgetify" plus its own differentiators returned nothing about
the app at all. Meanwhile the results for *"best offline expense tracker"* are
dominated by competitors' own blog posts — several apps rank three times over
with pages titled exactly like the query. Those pages are what search engines
return and what AI assistants retrieve and cite when someone asks for a
recommendation.

Each page therefore: puts the direct answer in the first paragraph, uses
question-shaped headings, includes a comparison table (structured content is
extracted far more reliably than prose), and carries `FAQPage` JSON-LD.

Two rules when editing them:

- **Every claim must be checkable.** The strongest asset here is that the
  no-`INTERNET`-permission claim can be falsified by a reader in a minute —
  that is *why* it gets repeated. Vague reassurance does not survive scrutiny
  and does not get cited.
- **State the limitations.** `ACCESS_NETWORK_STATE` is disclosed on the
  permission page even though it weakens the headline slightly, because a
  reader running `adb` will find it. Omitting it would turn a verifiable claim
  into a discovered omission. The same goes for no cross-device sync, no iOS
  version, and the small user base.

Do not add an `aggregateRating` to the JSON-LD until the app genuinely has
ratings. Inventing one is both a Google structured-data violation and a lie.

## Measuring whether it worked

```bash
python3 tools/ai_visibility.py                          # probe + reachability
python3 tools/ai_visibility.py --save snapshots/$(date +%F).json
python3 tools/ai_visibility.py --compare snapshots/2026-08-09.json
```

It asks Claude, ChatGPT, Gemini and Perplexity real user questions ("what's a
good offline expense tracker for Android in India?") and records whether the
reply names Budgetify. It probes only the providers whose API key is present in
the environment; with no keys at all it still runs the reachability checks,
which matter on their own — an assistant cannot cite a page it cannot fetch.

Scraping search engines was the obvious alternative and does not work: Google,
Bing and DuckDuckGo all return JavaScript shells to a plain HTTP client. Asking
the assistants directly is also the better measurement, because ranking in a
result list is not the same as being named in an answer.

Expect slow movement. Pages need to be indexed before they can be retrieved,
which takes weeks, and the two control prompts in the script ("what's the best
budgeting app?" and "what is Budgetify?") are there to keep expectations
honest at both ends.

## Local preview

Any static server will do — from the repo root:

```bash
python3 -m http.server 8000
```

Then open <http://localhost:8000/>.

## Deploying

Vercel builds this as a static site: no build command, no output directory,
framework preset **Other**. Pushes to `main` deploy to production; every
other branch and pull request gets its own preview URL.

`vercel.json` sets `trailingSlash: true` so the URLs match the ones GitHub
Pages served (`/privacy-policy/`, not `/privacy-policy`). That matters —
the Privacy Policy URL is registered in the Google Play Console, and the
relative paths inside each page resolve against the trailing slash.

### Two things that are not wired up yet

Both are dashboard tasks, not code, and the site's discovery work is largely
wasted until they are done:

1. **`budgetify.app` does not point at Vercel.** The domain is registered but
   its DNS still resolves to the registrar's parking IP, so nothing is served
   there. Add the domain in the Vercel project settings and set the DNS record
   it asks for at the registrar.
2. **The production deployment is login-protected.** The URL registered as the
   developer website on the Play listing currently redirects to a Vercel login
   page, so the public cannot reach the site. Turn off Deployment Protection
   (or add a public production alias) in the Vercel project settings.

Every `<link rel="canonical">`, the `sitemap.xml` entries and the `llms.txt`
links all point at `https://budgetify.app/` — the intended permanent home. They
are correct as written and start working the moment the domain resolves. If you
decide on a different production hostname instead, those three places are what
needs changing.

## Editing

Each page is a self-contained HTML file sharing `assets/style.css`. Change
the copy in place and push; there is nothing to compile. Adding a page means
adding it to `sitemap.xml` and to the tiles on `index.html` too — there is no
build step to do it for you.

The long-form Markdown source of the privacy policy still lives in the app
repository at `docs/privacy-policy.md`. If you edit the policy, update both
so they don't drift.
