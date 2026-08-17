# Methodology and decision register

## Scope and universe

The baseline covers 29 currencies: 11 developed-market currencies and 18 emerging-market currencies. USD is now an explicit currency rather than only the quote currency used by the raw BIS spot data.

| Group | Currencies |
|---|---|
| DM | USD, EUR, JPY, GBP, CHF, AUD, CAD, SEK, NZD, NOK, DKK |
| EM | CNY, HKD, INR, KRW, MXN, BRL, ZAR, PLN, IDR, TRY, THB, ILS, HUF, CZK, CLP, PHP, COP, MYR |

The selection is the liquid intersection of monthly BIS USD spot, broad real effective exchange rate (REER), and central-bank policy-rate data. The 2025 BIS Triennial Survey turnover ranking was used as the liquidity guide. The BIS coverage audit is reproducible with `scripts/audit_bis_coverage.py` and written to `data/processed/bis_coverage_audit.csv`.

Important exclusions:

- SGD and TWD are highly traded but do not have a compatible BIS policy-rate series in the chosen dataflow. Singapore implements policy primarily through its exchange-rate band.
- RUB is excluded from the baseline because sanctions, capital controls, market segmentation, and limited convertibility undermine a continuous investable-return interpretation.
- SAR and other hard pegs are excluded to avoid filling the cross-section with near-duplicate USD exposure. HKD remains included because of its high turnover and analytical relevance, but its peg must be considered when interpreting loadings.
- ARS is excluded because the BIS policy-rate history is stale and its multiple regime breaks require dedicated treatment.

The raw sample begins in January 1995. BIS broad REER begins in 1994, but the first half of 1994 contains Brazilian pre-Real hyperinflation policy rates above 10,000%, which dominate a policy-rate carry proxy. Starting in 1995 preserves more than 31 years while avoiding that discontinuity. Currencies enter when all required inputs become available; this is the expanding-universe convention used in much of the currency-factor literature.

## Data decisions

| Topic | Decision | Reason and consequence |
|---|---|---|
| Provider | Bank for International Settlements (BIS) for all inputs | A single official provider minimizes timing, convention, and revision mismatches. BIS permits reuse with attribution. |
| Spot | Monthly end-of-period local-currency units per USD | A rise means the foreign currency depreciates. The raw USD-investor spot return is `-diff(log(spot))`. |
| Value input | Monthly broad BIS REER, 2020=100 | REER combines nominal movements and relative CPI against 64 trade partners. A rise is a real appreciation. |
| Carry input | Month-end central-bank policy rate | This is an interim public proxy, not the tradable one-month forward discount used by canonical studies. |
| Analysis numeraire | Equal-weight basket of all available factor-eligible currencies | Makes every currency, including USD, symmetric and directly observable. Raw USD-bilateral returns are retained. |
| Missing rates | Forward-fill at most two monthly observations | Short publication gaps do not erase a return; longer gaps remain missing. Spot and REER are never forward-filled. |
| Revisions | Rebuild complete history on each forced weekly refresh | All downstream outputs remain internally consistent after BIS revisions. |

Official documentation: [BIS bilateral exchange rates](https://data.bis.org/topics/XRU), [BIS effective exchange rates](https://data.bis.org/topics/EER), [BIS central-bank policy rates](https://data.bis.org/topics/CBPOL), [BIS 2025 Triennial Survey](https://www.bis.org/statistics/rpfx25.htm), and [BIS permitted-use terms](https://data.bis.org/help/legal).

## Returns, basket numeraire, and USD

Let `x_i,t` be the log USD-investor excess return of currency `i`:

`x_i,t = -[s_i,t - s_i,t-1] + [r_i,t-1 - r_US,t-1] / 1200`

where `s` is log local-currency units per USD and policy rates are annual percentages. For USD, spot is one and the rate differential is zero, so `x_USD,t = 0` in the raw bilateral representation.

Let `A_t` be currencies with complete observations at `t`. The symmetric basket-relative return is:

`b_i,t = x_i,t - mean_j_in_A_t(x_j,t)`

Therefore `sum_j_in_A_t(b_j,t) = 0`. USD has a nonzero return `b_USD,t`, positive when USD strengthens against the equal-weight basket. Both `x_i,t` and `b_i,t` are retained in `currency_panel.csv`; factor construction and currency decomposition use `b_i,t`.

The explicit dollar factor follows the literature-standard portfolio:

`Dollar_t = mean_i_not_USD(b_i,t) - b_USD,t = mean_i_not_USD(x_i,t)`

It is long an equal-weight foreign-currency basket and short USD. A positive dollar-factor return means broad USD weakness. Because USD is one leg of this factor, USD's loading on it is mechanically close to `-(N-1)/N`, and USD idiosyncratic variance is nearly zero when the dollar factor is included. This is an identity, not evidence that USD has no independent economic shocks.

For the full design comparison, see `docs/NUMERAIRE_DESIGN.md`.

## Style factors

All signals used for month `t` are known at the end of `t-1`.

### Carry

Signal: lagged absolute policy rate. Ranking by the absolute rate is equivalent to ranking by a differential against any common numeraire, and it permits USD to participate naturally. Go long the highest-rate currencies and short the lowest-rate currencies.

Canonical work uses one-month forward discounts. Policy rates preserve the high-versus-low monetary stance but are not investor funding rates, especially in managed or segmented EM markets.

### Momentum

Signal: cumulative basket-relative excess return over the prior three completed months. Go long prior winners and short prior losers.

### Value

Signal: `log(mean(REER[t-67:t-55])) - log(REER[t-1])`. The 13-month historical average is centered about five years before formation. A positive signal means the current REER is weak relative to its own history and the currency is classified as cheap.

This uses changes in REER, not its index level. BIS explicitly cautions that a level above or below 100 does not itself imply over- or undervaluation.

### Portfolio construction

For carry, value, and momentum independently:

1. Drop currencies missing the signal or current basket-relative return.
2. Require at least six currencies.
3. Sort from low to high signal.
4. Equal-weight the top third to +1 and bottom third to -1.
5. Leave the middle third at zero.

The portfolios have zero net currency weight and gross exposure of two. For any zero-net-weight portfolio, subtracting a common numeraire return from every currency cancels exactly. Consequently, carry, value, and momentum factor returns are invariant to choosing USD or the equal-weight basket, conditional on the same membership.

The dollar portfolio equal-weights all available foreign currencies to +1 in total and assigns USD -1.

## Currency decomposition

For each currency, including USD, the dashboard estimates:

`b_i,t = alpha_i + beta_Dollar,i Dollar_t + beta_Carry,i Carry_t + beta_Value,i Value_t + beta_Momentum,i Momentum_t + epsilon_i,t`

- Full-sample coefficients use OLS with Newey-West/HAC inference and three monthly lags.
- Time-varying coefficients use rolling 60-month windows and require at least 48 observations.
- Annualized idiosyncratic volatility is residual standard deviation times `sqrt(12)`.
- Idiosyncratic variance share is `1 - R-squared`, bounded to `[0,1]` for display.
- All factors contain some test currencies, creating self-inclusion. This is strongest and mechanical for USD versus the dollar factor. Leave-one-out factors are a recommended robustness extension.

## ARMA forecasts

Dollar, carry, value, and momentum returns are modeled independently as ARMA(p,q), implemented as ARIMA(p,0,q) with a constant. Candidate orders are `p,q in {0,1,2}` and the lowest-AIC converged model is selected. Forecasts cover 12 months with 80% and 95% conditional prediction intervals.

These are diagnostic baselines. They do not incorporate model-selection uncertainty, structural breaks, non-normal tail risk, or transaction costs.

## References and rationale

- Lustig, Roussanov, and Verdelhan (2011), *Common Risk Factors in Currency Markets*, establishes the dollar and carry factor framing.
- Aloosh and Bekaert (2022), *Currency Factors*, motivates currency baskets and models designed to work beyond one USD perspective.
- Fan, Kearney, Li, and Liu (2026), in the workspace, summarizes standard carry, three-month momentum, and five-year real-exchange-rate value implementations.
- The BIS 2025 Triennial Survey supplies the current liquidity ranking used for universe selection.

## Deferred upgrades

- replace policy-rate carry with one-month forward points or matched tradable short rates;
- create an investability overlay for onshore, offshore, NDF, peg, and capital-control regimes;
- add turnover-based or risk-balanced basket weights alongside the equal-weight baseline;
- add leave-one-currency-out exposures;
- add bid/ask spreads, turnover, transaction costs, and volatility scaling;
- evaluate forecasts strictly out of sample;
- define executable instrument mapping and governance before producing positions.

