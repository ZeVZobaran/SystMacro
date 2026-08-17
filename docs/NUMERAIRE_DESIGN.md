# Numeraire design

Exchange rates are relative prices, so choosing one currency as the quote currency changes the apparent common component of bilateral returns. It does not change a correctly constructed zero-net-weight long-short portfolio, but it does change individual-currency time series, correlations, PCA results, and regression interpretation.

## Alternatives considered

| Representation | Construction | Advantages | Limitations | Role in SystMacro |
|---|---|---|---|---|
| USD bilateral | Foreign-currency return versus USD | Tradable and familiar to USD investors; matches much of the literature | USD is implicit and every series contains the same USD shock | Retained as `excess_return_usd` for audit and investor views |
| Equal-weight basket | Subtract the cross-sectional mean return each month | Symmetric, transparent, zero-sum, and gives USD its own series | Basket membership and weights can change as coverage changes | Default analytical numeraire |
| Trade-weighted basket | Use trade shares or BIS effective-exchange-rate weights | Strong macro competitiveness interpretation | Weights are country-specific, lagged, and not one common global portfolio | Future robustness view |
| SDR basket | Use IMF SDR weights | Stable, public, and institutionally recognizable | Concentrated in five currencies and not representative of the full FX market | Optional benchmark, not baseline |
| Turnover-weighted basket | Weight by BIS FX turnover | Better reflects market liquidity | Highly USD-dominated and updated only triennially | Candidate market benchmark |
| Pairwise graph/network | Model all `N(N-1)/2` cross-rates or recover latent currency nodes | Closest to numeraire-free; captures clusters and networks | High dimensional, harder to identify and explain | Research extension |
| Currency baskets / latent factors | Build each currency against all others and estimate world/cluster factors | Designed to work across currency perspectives | More estimation choices and less direct portfolio interpretation | Research extension inspired by Aloosh-Bekaert |

## Why equal weight is the baseline

Equal weighting is the smallest change that fixes the original asymmetry without importing a new weighting dataset or estimation model. Every eligible currency receives the same ex ante role. USD appears explicitly, basket returns sum to zero, and the original USD-bilateral return remains available.

For currency `i`, raw USD excess return is `x_i`. The basket return is `b_i = x_i - mean(x)`. If a portfolio has weights `w` with `sum(w)=0`, then:

`sum(w_i b_i) = sum(w_i x_i) - mean(x) sum(w_i) = sum(w_i x_i)`

Thus the carry, value, and momentum long-short returns are numeraire invariant. What changes is the decomposition of each individual currency and the ability to display USD as an asset.

## Interpretation of the dollar factor

The dollar factor is long the equal-weight foreign basket and short USD. Positive means foreign currencies appreciate on average versus USD; equivalently, USD weakens broadly. The displayed USD basket return has the opposite sign and is scaled by the number of available currencies.

The near-perfect inverse relation is deliberate. It makes the previously hidden USD component visible. It also means the USD regression residual against a model containing the dollar factor is mechanically tiny; that diagnostic should not be interpreted as an economic forecast-error result.

## Membership and robustness

The available basket expands when a currency obtains complete spot, rate, and REER inputs. Each output records the available count. A future robustness dashboard should compare:

1. the dynamic full universe;
2. a balanced panel beginning when all 29 currencies are available;
3. DM-only and EM-only baskets;
4. equal-weight and turnover-weight benchmarks;
5. leave-one-out basket returns for loading estimation.

