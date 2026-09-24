# Out-of-Sample / Walk-Forward Validation - XAUUSD_M15_56202

No additional history beyond the 24 months in data/raw is available in this
repository, so the walk-forward test slices the SAME continuous full-period
simulation by entry month (risk gates and capital therefore behave exactly as
in production; OOS trades are truly never used for any calibration).

## Fold 1 - train 2024-09..2025-08, test (OOS) 2025-09..2026-02

| segment | trades | WR | PF | return% | avg pnl% |
|---|---:|---:|---:|---:|---:|
| train | 119 | 63.9% | 1.76 | +8.75% | +0.074% |
| **test (OOS)** | 36 | 77.8% | 2.97 | +5.61% | +0.156% |

## Fold 2 - train 2025-03..2026-02, test (OOS) 2026-03..2026-08

| segment | trades | WR | PF | return% | avg pnl% |
|---|---:|---:|---:|---:|---:|
| train | 88 | 70.5% | 1.95 | +7.96% | +0.090% |
| **test (OOS)** | 21 | 52.4% | 0.76 | -0.84% | -0.040% |

## Year-split performance

| period | trades | WR | PF | return% |
|---|---:|---:|---:|---:|
| 2024-09..2025-12 | 146 | 66.4% | 1.92 | +13.03% | +0.089% |
| 2026-01..2026-09 | 32 | 59.4% | 1.08 | +0.34% | +0.011% |
| full period | 178 | 65.2% | 1.73 | +13.36% | +0.075% |

Note: return% is measured against the flat $10,000 baseline (same convention
as the Phase-10 reports); because trades overlap with equity growth, the OOS
segment values are diagnostics on the trade stream, not standalone equity
returns.
