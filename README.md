# SMB Adoption Health Check

A small Python tool that reads RFI and submittal data through the Procore API and turns it into a one page **Customer Value Review**: a health score with the reasons behind it, the key numbers, three specific recommendations, and a 30/60/90 day adoption plan.

It is built the way a Customer Success Engineer would use it: pull the data before a check-in, see where adoption is slipping, and walk the customer through what to fix.

> Independent portfolio project. Built on the Procore Developer Sandbox with sample data. Not affiliated with or endorsed by Procore.

## What it measures

| Area | Metrics |
|---|---|
| RFIs | Open, overdue, open without a due date, average days to close, oldest open item, ball in court on open and overdue items |
| Submittals | Open, overdue (including revise and resubmit), open without a due date, average days to close |
| Health score | Starts at 100. Points come off for overdue RFIs, overdue submittals, RFI turnaround slower than 7 days, and open items without due dates. Every deduction is shown on the report. |

## Try it without an account

```bash
pip install -r requirements.txt
python -m health_check demo
```

Open `output/value_review_demo.html` in a browser (print to PDF for a one pager).

## Run it on the Procore Developer Sandbox

1. **Create a free developer account** at https://developers.procore.com/signup and verify your email.
2. **Create an app**: My Apps > Create New App.
3. **Add a component**: Data Connector Components > Add Components > User-level Authentication > Save. Then click **Create Version**.
4. **Set the redirect URI**: OAuth Credentials > Sandbox OAuth Credentials > Redirect URI = `urn:ietf:wg:oauth:2.0:oob`
5. **Install the app in your sandbox company**: sign in to the sandbox, then Company Tools > Admin > App Management > Install App > Install Custom App, and paste the Sandbox App Version Key.
6. **Add credentials**: copy `.env.example` to `.env` and fill in the Sandbox Client ID and Client Secret.
7. **Authenticate**: `python -m health_check auth`, open the printed URL, click Allow, paste the code.
8. **Find your IDs**: `python -m health_check projects`
9. **Check field names**: `python -m health_check dump --company-id C --project-id P`, then look at `output/raw_rfis.json`. If date or status keys differ from what `FIELD_CANDIDATES` in `health_check/metrics.py` expects, add them there.
10. **Build the report**: `python -m health_check run --company-id C --project-id P --customer "Sandbox Company"`

The sandbox starts with one RFI and one submittal, so add 10 to 15 realistic RFIs and 8 to 10 submittals in the Procore web app first (some closed, some open, a few past due). That is also good practice in the tools themselves.

## Tests

```bash
python -m pytest -q
```

## Project layout

```
health_check/
  metrics.py   pure functions: summaries, score, recommendations, plan (tested)
  procore.py   OAuth (sandbox) and paginated API client
  report.py    one page HTML report
  __main__.py  command line: demo, auth, projects, dump, run
sample_data/   synthetic RFIs and submittals for the demo
tests/         unit tests for the metrics
```

## Design choices

- **Rules, not AI**, for the score and recommendations, so every number can be explained to a customer in one sentence.
- **Read only.** The tool never writes to Procore.
- **Secrets stay local.** `.env` and `.tokens.json` are git ignored.
