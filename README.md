# 0xRadikal.github.io

Host-root files for `https://0xradikal.github.io/`.

GitHub Pages serves every project site of this account under this host
(`/Free-Telegram-Proxy/`, `/Free-v2ray-Configs/`, `/profile-card/`). Some
things only work from the host root, so they live here:

| File | Why it must be at the root |
|---|---|
| `robots.txt` | Crawlers read robots.txt only from the host root (RFC 9309). Allows everything and lists the sitemaps. Only the four standard fields are used (`user-agent`, `allow`, `disallow`, `sitemap`); the [Content Signals](https://contentsignals.org/) policy is stated as a comment, because a `Content-Signal:` line is reported as an error by Bing's tester, Lighthouse and Search Console. |
| `sitemap.xml`, `sitemap-root.xml` | Sitemap index pointing at each project's sitemap plus the host-level pages. |
| `index.html` + icons | Google shows one favicon and one site name per hostname, taken from the host home page. Without it every project shows a generic icon. |
| `llms.txt` | Root guide for AI agents ([llmstxt.org](https://llmstxt.org/)); links each project's own `llms.txt`. |
| `.well-known/security.txt` | RFC 9116 security contact (`/.well-known/` exists only at the root). `Expires` must be renewed yearly - CI fails 30 days before. |
| `48598d5aeac99302a1fe588536e080dc.txt` | [IndexNow](https://www.indexnow.org/) key (public by design) so project sites can notify Bing/Yandex of changes. |
| `.nojekyll` | Serve files exactly as committed (needed for `.well-known/`). |

There is intentionally no `404.html`, so nothing here changes how missing
pages inside the project sites behave. `tools/check.py` validates every file
(and, with `--live`, the deployed site); CI runs it on every push and weekly.
