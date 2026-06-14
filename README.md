# Upstox Options Lab

Fetches NIFTY & BANKNIFTY option chain with IV and Greeks every 15 minutes during market hours using Upstox API and GitHub Actions.

## Setup

1. Get your Upstox Algo Trading token from [developer dashboard](https://upstox.com/developer/).
2. Add it as a GitHub secret: `UPSTOX_ACCESS_TOKEN`.
3. Push to a public repository – the workflow runs automatically.

## Output

CSV files saved in `data/` folder (available as workflow artifacts).