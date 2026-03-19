# Phase 2 Summary — Individual Gap Results

| Gap | Name | Sharpe | Return% | MaxDD% | MR PnL | Overrides |
|-----|------|--------|---------|--------|--------|-----------|
| 1-stop | stop_5_base | 1.61 | 3150% | 24.8% | +2,774,798 | {} |
| 1-stop | stop_20 | 1.47 | 1800% | 25.7% | +254,075 | {"stop_pct": 20} |
| 1-stop | stop_10 | 1.33 | 1410% | 28.7% | +683,716 | {"stop_pct": 10} |
| 1-stop | no_stop_timeout10 | 1.28 | 1119% | 30.4% | +143,727 | {"stop_pct": null, "timeout_days": 10} |
| 1-stop | stop_50 | 1.27 | 1037% | 24.7% | +223,019 | {"stop_pct": 50} |
| 1-stop | stop_15 | 1.26 | 1062% | 24.4% | -7,064 | {"stop_pct": 15} |
| 1-stop | no_stop_timeout8 | 1.21 | 906% | 33.8% | -76,185 | {"stop_pct": null, "timeout_days": 8} |
| 1-stop | no_stop | 1.12 | 780% | 23.6% | +260,890 | {"stop_pct": null} |
| 1-stop | no_stop_timeout15 | 1.12 | 780% | 23.6% | +260,890 | {"stop_pct": null, "timeout_days": 15} |
| 1-stop | stop_30 | 1.10 | 739% | 23.5% | +227,077 | {"stop_pct": 30} |
| 1-stop | no_stop_timeout12 | 1.07 | 628% | 31.1% | +78,964 | {"stop_pct": null, "timeout_days": 12} |
| 1-stop | stop_25 | 1.06 | 649% | 23.7% | +149,427 | {"stop_pct": 25} |
| 2-adx | adx_lt30 | 1.69 | 3307% | 24.1% | +2,874,462 | {"require_adx": true, "adx_max": 30} |
| 2-adx | no_adx_base | 1.61 | 3150% | 24.8% | +2,774,798 | {} |
| 2-adx | adx_lt25 | 1.36 | 1433% | 25.3% | +735,872 | {"require_adx": true, "adx_max": 25} |
| 2-adx | adx_lt35 | 1.26 | 1253% | 27.3% | +1,779,903 | {"require_adx": true, "adx_max": 35} |
| 2-adx | adx_lt20 | 1.09 | 740% | 31.1% | -15,223 | {"require_adx": true, "adx_max": 20} |
| 3-cumrsi | rsi_single5_base | 1.61 | 3150% | 24.8% | +2,774,798 | {} |
| 3-cumrsi | rsi_cum3_15 | 1.55 | 2658% | 26.7% | +3,471,913 | {"rsi_mode": "cum3", "rsi_entry": 15} |
| 3-cumrsi | rsi_cum2_10 | 1.45 | 2073% | 24.8% | +2,124,757 | {"rsi_mode": "cum2", "rsi_entry": 10} |
| 4-rsi_exit | rsi_exit_75 | 1.70 | 4088% | 25.2% | +3,352,805 | {"rsi_exit": 75} |
| 4-rsi_exit | rsi_exit_65_base | 1.61 | 3150% | 24.8% | +2,774,798 | {} |
| 4-rsi_exit | rsi_exit_60 | 1.58 | 2706% | 24.3% | +2,055,140 | {"rsi_exit": 60} |
| 4-rsi_exit | rsi_exit_80 | 1.58 | 2945% | 25.9% | +2,871,011 | {"rsi_exit": 80} |
| 4-rsi_exit | rsi_exit_70 | 1.35 | 1830% | 36.0% | +1,693,980 | {"rsi_exit": 70} |
| 4-rsi_exit | rsi_exit_0 | 1.16 | 1001% | 31.4% | +1,129,689 | {"rsi_exit": 0} |
| 5-trend | trend_none_base | 1.61 | 3150% | 24.8% | +2,774,798 | {} |
| 5-trend | trend_sma200 | 1.34 | 1365% | 30.4% | +943,176 | {"trend_filter": "sma200"} |
| 5-trend | trend_sma50 | 1.24 | 943% | 28.7% | +185,516 | {"trend_filter": "sma50"} |
| 5-trend | trend_sma50_slope | 1.04 | 619% | 26.5% | +150,300 | {"trend_filter": "sma50_slope"} |