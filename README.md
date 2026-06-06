# Walmart Restock Monitor

Sends you a push notification when a Walmart product goes from out-of-stock to
in-stock. Uses ntfy.sh (free, no account needed). Runs free on GitHub Actions,
checking roughly every 15-30 minutes.

## File layout in your repo

```
your-repo/
├─ monitor.py
├─ requirements.txt
└─ .github/
   └─ workflows/
      └─ monitor.yml   <-- the file named monitor.yml goes HERE
```

(`state.json` is created automatically on the first run — don't add it yourself.)

## One-time setup (~15 min)

1. **Create a new GitHub repo and make it Public.**
   Public repos get unlimited Actions minutes, so the schedule costs nothing.
   Your code being public is fine — no secrets live in the files.

2. **Add the three files** above, putting `monitor.yml` inside
   `.github/workflows/`.

3. **Set up push notifications with ntfy.sh (free, no account):**
   - Install the **ntfy** app on your phone ([iOS](https://apps.apple.com/app/ntfy/id1625396347) / [Android](https://play.google.com/store/apps/details?id=io.heckel.ntfy)).
   - Open the app, tap **+**, and subscribe to a topic name you make up — something
     random like `walmart-restock-abc123`. This is your channel; anyone who knows
     the name can send to it, so make it hard to guess.
   - That topic name is the only secret you need.

4. **Add your secrets.** Repo → Settings → Secrets and variables → Actions →
   "New repository secret". Add:

   | Secret name        | Value                                            |
   |--------------------|--------------------------------------------------|
   | `PRODUCT_URL`      | the clean product URL (see note below)           |
   | `NTFY_TOPIC`       | your ntfy topic name, e.g. `walmart-restock-abc123` |

   (Add `SCRAPER_API_KEY` later only if you get blocked — see below.)

   **For `PRODUCT_URL`, use the clean canonical link — drop the
   `?action=SignIn&rm=true&sid=...` tracking junk:**

   ```
   https://www.walmart.com/ip/Nongshim-Soon-Veggie-Savory-Vegan-Ramyun-Ramen-Noodle-Soup-Pack-3-95oz-X-10-Count/37204315
   ```

   The script reads the item number (`37204315`) from the end of that URL.

5. **Test it.** Actions tab → enable workflows if prompted →
   "walmart-restock-monitor" → "Run workflow". Open the run and read the log:
   - `Detected in_stock=False (item 37204315: OUT_OF_STOCK)` — working
     correctly. It'll text you when that flips to `IN_STOCK`.
   - `Detected in_stock=None (no node matched item ...; found instead: ...)` —
     the item-ID match missed. Send me that log line and I'll pin the parser.
   - `BLOCKED ...` — see anti-bot note below.

That's it. Leave it running.

## Known caveats (the honest list)

- **Anti-bot blocks.** Walmart may block the GitHub runner's IP. If logs show
  `BLOCKED` repeatedly, sign up for a scraping API (e.g. ScraperAPI / ScrapingBee
  free tier) and add its key as the `SCRAPER_API_KEY` secret — the script will
  route through it automatically. Check the provider's current free-credit
  limit; at 15-min checks you make ~2,900 requests/month.
- **Multi-variant page.** Your item has size/pack variants and a "similar
  items" carousel, so the script keys off the exact item number rather than
  page text. If Walmart renames the JSON field it reads, detection returns
  "undetermined" and logs what it found (it won't send a wrong alert).
- **60-day inactivity.** GitHub auto-disables scheduled workflows if the repo
  gets no commits for 60 days. If yours goes quiet that long, push any commit
  to re-arm it.
- **Online vs. store pickup.** This watches the online "ship to me" stock on the
  page. Store-pickup availability is tracked separately by Walmart.
- **Scheduled-run timing isn't exact.** GitHub can delay crons under load, so
  treat "every 15 min" as "every 15-30 min."
