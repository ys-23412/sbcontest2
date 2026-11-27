Scrapping sites and downloads information to upload to the apis, bcbid under progress.

## BC Bid: proxy failures and the "Browser check"

BC Bid now opens a fresh pydoll v3 browser per attempt:

1. `squid` — the shared Squid proxy on the GCP VM, read from the `PROXY_URL`
   environment variable (the `PROXY_URL_WITH_PASS` secret in GitHub Actions).
   Skipped when `PROXY_URL` is not set.
2. `direct` — no proxy. The fallback, so a dead proxy never takes the whole run down.
3. `open-proxy-1..N` — **opt-in** free proxies from `web_requests.get_proxy_list()`,
   health-checked against BC Bid first.

IPRoyal is not used for BC Bid. `IPROYAL_*` variables are ignored by this
scraper even when they are set.

A browser-check block or a proxy connection error (`ERR_PROXY_CONNECTION_FAILED`,
`ERR_TUNNEL_CONNECTION_FAILED`, `ERR_TIMED_OUT`, ...) moves on to the next attempt.
Each attempt launches Chrome on its own proxy. The proxy login stays in the URL
(`http://user:pass@host:port`): pydoll takes it off the Chrome command line and
answers the proxy itself. It is never printed or sent to Discord.

Only the first `BCBID_MAX_ATTEMPTS` entries of that list are tried. By default
that is squid, then direct (two attempts); the third slot is only filled when
open proxies are switched on. With `BCBID_MAX_ATTEMPTS=1` only squid is tried.
Only the final failure pages Discord and fails the job; evidence from that attempt
is saved to `screenshots/browser_check_blocked.html/.png`.

Tuning (all optional env vars):

| Variable | Default | Purpose |
| --- | --- | --- |
| `BCBID_MAX_ATTEMPTS` | `3` | How many attempts to make |
| `BCBID_ATTEMPT_PAUSE` | `5` | Seconds between attempts |
| `BCBID_USE_OPEN_PROXIES` | `0` | Set to `1` to try free proxies as a last resort |
| `BCBID_OPEN_PROXY_LIMIT` | `2` | Max free proxies to health-check |
| `BCBID_BROWSER_CHECK_WAIT` | `30` | Seconds to wait for the check to pass |

### reCAPTCHA v3 — what pydoll can and cannot do

BC Bid's check page is an **invisible reCAPTCHA v3**: it calls
`window.ivCaptcha.solve()` → `grecaptcha.execute()` → fills `#captcha_response`
→ submits `mainForm`. There is no puzzle to click and no answer to compute.

Pydoll v3's captcha helper is Cloudflare Turnstile **only**; its own docs say
"It does not handle reCAPTCHA or hCaptcha". The scraper therefore only waits on
the check page, with pydoll's humanized mouse/scroll input, and if the check
still refuses it the runner starts a new browser on the next connection.
Free open proxies exist (already used by `web_requests.py`) but they are slow
and widely blocked, so they are opt-in and last.

### No pydoll profiles

The scraper uses neither kind of profile:

- **Fingerprint profile** (`tab.apply_fingerprint()`): optional in pydoll, which
  ships none ("bring your own"). Its docs say a profile has to describe the real
  machine and exit IP, and that an inconsistent one is worse than an untouched
  browser. Applying one also stops pydoll answering the proxy login, so every
  navigation through the Squid proxy fails with `ERR_INVALID_AUTH_CREDENTIALS`.
- **Saved browser profile** (a Chrome user-data directory): pydoll starts each
  browser in a temporary one, and nothing here needs state between runs.


For the proxy used, we setup a free google cloud platform and the following instructions

To set up a simple authenticated proxy on Google Cloud Platform (GCP) for use with Chrome, the most reliable and "lightweight" method is deploying a **Squid Proxy** on a small Compute Engine instance. My plan is turn off the instance if it gets blocked and then turn it back on (getting a new ip address in the process), also swap between linux, windows and mac osx. 

Alternative to google cloud platform is oracle always free tier, use a new micro, signup.

### **Phase 1: Create the GCP Instance**

1.  Go to the [GCP Console](https://console.cloud.google.com/) and navigate to **Compute Engine \> VM Instances**.
2.  Click **Create Instance**.
3.  **Machine configuration:** Select **e2-micro** (this is usually enough for a personal proxy).
4.  **Boot disk:** Choose **Ubuntu 22.04 LTS** or **24.04 LTS**.
5.  **Firewall:** Check **Allow HTTP traffic** (we will manually open the proxy port later).
6.  Click **Create**.

-----

### **Phase 2: Install and Configure Squid**

Once the VM is running, click the **SSH** button next to it to open a terminal. Run the following commands:

#### **1. Install Squid and Utilities**

```bash
sudo apt-get update
sudo apt-get install squid apache2-utils -y
```

#### **2. Create the Password File**

Replace `your_username` with the name you want to use. You will be prompted to enter and confirm a password.

```bash
sudo htpasswd -c /etc/squid/passwords your_username
```

#### **3. Configure Squid for Authentication**

Open the config file:

```bash
sudo nano /etc/squid/squid.conf
```

Scroll to the very top and paste these lines **above** all other rules:

```text
auth_param basic program /usr/lib/squid/basic_ncsa_auth /etc/squid/passwords
auth_param basic realm Squid proxy
auth_param basic credentialsttl 24 hours
auth_param basic casesensitive off

acl authenticated proxy_auth REQUIRED
http_access allow authenticated
http_port 3128
```

*Press `Ctrl+O`, `Enter`, then `Ctrl+X` to save and exit.*

#### **4. Restart Squid**

```bash
sudo systemctl restart squid
```

-----

### **Phase 3: Open the Firewall in GCP**

By default, GCP blocks port `3128`. You must open it:

1.  In the GCP Console, search for **VPC Network \> Firewall**.
2.  Click **Create Firewall Rule**.
3.  **Name:** `allow-proxy`
4.  **Targets:** `All instances in the network`
5.  **Source IPv4 range:** `0.0.0.0/0` (Note: For better security, use your own home/office IP instead).
6.  **Protocols and ports:** Check **TCP** and enter `3128`.
7.  Click **Create**.

-----

### **Phase 4: Connect with Chrome with pydoll**

use the following format user:pass@external_ip_address:port in pydoll and save as a variable PROXY_URL_WITH_PASS