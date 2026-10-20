# Answer key (fictional test data)

All businesses, receipts and transactions are made up.

## Receipts (what the AI should read)

| File | Vendor | Date | Total |
|---|---|---|---|
| 01-northgate-fuel.jpg | Northgate Fuel #12 | 10/02/2026 | $53.56 |
| 02-main-street-hardware.jpg | Main Street Hardware | 10/03/2026 | $129.12 |
| 03-precision-auto.jpg | Precision Auto Parts | 10/06/2026 | $44.61 |
| 04-harbor-grill.jpg | Harbor Grill | 10/08/2026 | $36.84 |
| 05-summit-office.jpg | Summit Office Supply | 10/10/2026 | $23.19 |

## Planted problems (what the agent should catch)

1. **Duplicate charge:** Main Street Hardware charged $129.12 twice (10/03 and 10/04), but there is only one receipt.
2. **Amount mismatch:** Harbor Grill receipt is $36.84, bank charge is $43.84 (a $7.00 tip added after signing).
3. **Missing receipt:** Brightline Print & Sign charged $75.00 on 10/16 and there is no receipt.

## Other things to check

- The $2,400.00 mobile deposit is income and should be skipped, not flagged.
- Bank dates can be 1 day after the receipt date (Precision Auto Parts, Harbor Grill). These should still match.
- Bank names are abbreviated ("MAIN ST HDWE" = Main Street Hardware).
