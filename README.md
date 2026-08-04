# budgetify.app

The public website for **Budgetify** — the FAQ, the Privacy Policy, and the
data-deletion instructions.

Split out of the app repository
([Yolo-cell-hash/budgetify](https://github.com/Yolo-cell-hash/budgetify)),
where it used to live in `docs/` and was served by GitHub Pages. The app's
source stays there; this repo is only the site.

## What's here

```
index.html            landing page
faq/                  FAQ
privacy-policy/       Privacy Policy  ← the URL registered with Google Play
data-deletion/        how to erase your data
assets/               stylesheet, app icon, Manrope font files
vercel.json           trailing-slash + cache/security headers
```

Plain static HTML and CSS. No build step, no framework, no dependencies —
every path is relative, so it works the same served from a subdirectory or
from the domain root. Fonts are self-hosted (see `assets/fonts/OFL.txt`);
nothing is fetched from a third party, which keeps the site as free of
tracking as the app it describes.

## Local preview

Any static server will do — from the repo root:

```bash
python -m http.server 8000
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

## Editing

Each page is a self-contained HTML file sharing `assets/style.css`. Change
the copy in place and push; there is nothing to compile.

The long-form Markdown source of the privacy policy still lives in the app
repository at `docs/privacy-policy.md`. If you edit the policy, update both
so they don't drift.
