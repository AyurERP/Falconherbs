# Director se kaise baat karein

**Ye guide tumhein batata hai — Director ko WhatsApp pe kya bhejna hai, kaise bhejna hai.**

Director = Falcon Agency ka AI. Tum WhatsApp pe message bhejoge, Director samjhega aur kaam karega. Yeh document tumhein saare working prompts dikhata hai.

---

## Flow (samajh lo)

```
Tum (WhatsApp)  →  Director  →  Agents (WooCommerce, Health, Content, etc.)
```

**Tum directly agents ko nahi bolte.** Tum sirf Director ko bolte ho. Director andar se sahi agent/tool use karta hai.

---

## Health & Compliance

| Tum bhejo | Director kya karega |
|-----------|---------------------|
| `health scan` | Full site audit — products, blogs, pages, categories (WooCommerce + WP API se) |
| `health scan karo` | Same |
| `scan products` | Sirf products check — descriptions, titles, image alt |
| `scan blogs` | Sirf blog posts check |
| `scan pages` | Sirf WordPress pages check |
| `sab fix karo` | **Confirm chahiye** — phir sab violations fix (products + blogs + pages + categories) |
| `push karo` | **Confirm chahiye** — product rewrites apply |
| `rewrite products` | AI se product descriptions fix karke draft banao |
| `changelog` | Last fix report dikhao |

**Confirm flow:** Jab Director "Confirm karein" bole, tum bolo: `haan karo` / `yes do it` / `kar do` / `theek hai`

---

## Store & Sales

| Tum bhejo | Director kya karega |
|-----------|---------------------|
| `store status` | WooCommerce audit — kitne products, API OK? |
| `order check` | Recent orders — kitne aaye, revenue |
| `kitne order aaye` | Same |
| `revenue` | Sales summary — aaj, mahine |
| `profit report` | Munafa, ROI |
| `payment check` | Payment gateway status |

---

## Content

| Tum bhejo | Director kya karega |
|-----------|---------------------|
| `blog likh about [topic]` | Blog draft banao (e.g. "blog likh about ashwagandha benefits") |
| `social post about [topic]` | Instagram/FB post + caption |
| `content status` | Pending drafts dikhao |
| `drafts dikhao` | Same |
| `publish karo` | Latest draft WordPress pe publish (draft mode) |
| `publish live karo` | **Confirm chahiye** — phir LIVE publish |
| `live karo` | Same (confirm ke baad) |
| `content package` | Weekly content package (images, captions, video) HeroPost ke liye |

---

## Status & Reports

| Tum bhejo | Director kya karega |
|-----------|---------------------|
| `sab batao` | Full status — tasks, spend, recent activity |
| `status` | Workforce update |
| `morning report` | Same |
| `kya ho raha hai` | Same |
| `help` | Saare commands list |
| `kya kar sakte ho` | In-scope vs out-of-scope capabilities |

---

## Transparency & Team (Boss Report)

| Tum bhejo | Director kya karega |
|-----------|---------------------|
| `agent performance` | Kaun kitna kaam kar raha — busy vs idle agents |
| `kaun kitna kaam kar raha` | Same — 7-day performance report |
| `transparency report` | Same |
| `director complaint` | Problem report — failures, idle agents |
| `director ko complaint` | Same |
| `@aeo scan` / `@aeo report` | Direct AEO agent se baat |
| `@developer` / `@strategist` / `@media` / `@backup` | Direct agent se baat |

---

## Server / Site Down

| Tum bhejo | Director kya karega |
|-----------|---------------------|
| `site down` | Server diagnostic — reachability, WHM status |
| `server diagnose` | Same |
| `kya problem hai site` | Same |

**Maintenance mode:** `.env` mein `MUTE_SITE_ALERTS=1` add karo — Director site-down alerts band karega.

---

## WordPress Admin (WP REST API se)

Director ke paas WP admin access hai — ye sab WhatsApp se kar sakta hai:

| Tum bhejo | Director kya karega |
|-----------|---------------------|
| `plugin list` | Installed plugins dikhao |
| `plugin install [name]` | Plugin install (approval + backup pehle) |
| `plugin update` | Pending plugin updates karo |
| `plugin recommend` | Speed/SEO/security ke liye suggest |
| `sab fix karo` | Blog + page + product title fixes apply |
| `push karo` | Product rewrites apply |
| `publish karo` | Draft WordPress pe publish |
| `drafts dikhao` | Pending drafts list |
| `health scan` | Full site — products, blogs, pages |
| `scan blogs` / `scan pages` | Sirf blogs ya pages |

**Note:** Blog/page fixes ke liye `.env` mein `FALCONHERBS_WP_APP_PASSWORD` hona chahiye (quotes mein: `"xxxx xxxx xxxx xxxx"`).

---

## Backup & System

| Tum bhejo | Director kya karega |
|-----------|---------------------|
| `backup banao` | Site backup create |
| `backup list` | Backup registry |
| `backup verify` | Last backup verify |

---

## SEO, Competitor, Ads

| Tum bhejo | Director kya karega |
|-----------|---------------------|
| `seo audit` | Full SEO check |
| `competitor check` | Competitor analysis |
| `ads status` | Paid ads info |
| `price scan` | Competitor price scan |
| `aeo scan` | AEO brand visibility scan |

---

## Tips — Director ke saath baat karne ke

1. **Simple bolo** — "health scan" kaafi hai, "please kripya health scan karo" ki zarurat nahi
2. **Confirm pe** — Jab Director "haan karo" bole, tum bolo: `haan karo` / `yes` / `kar do`
3. **Topic ke saath** — "blog likh about X" — X mein topic daalo
4. **Hinglish chalega** — "sab batao", "kitne order aaye", "revenue batao" — sab samjhega

---

## Example — Health scan ka full flow

**Tum:** `health scan karo`

**Director:** (2–5 min) — Report bhejega: products, blogs, pages, categories. Kya fix karna hai, kya nahi.

**Tum:** `sab fix karo`

**Director:** Confirm karein? Ye sab LIVE site par apply karega. Type 'haan karo' to confirm.

**Tum:** `haan karo`

**Director:** (fix karega) — Done. Report bhejega.

---

*Ye guide tumhein Director ke saath communicate karne mein help karega. Naya prompt add karna ho toh batao.*
