# Carrier B: usage records, mobile line

*Invented for Mabillon's synthetic evaluation. Carrier B is not a real carrier, and this guide
copies no real carrier's documentation.*

Carrier B returns usage records for the requested mobile number as a CSV file with one header
row. The sample is `samples/carrier-b.csv`.

| Column | Meaning |
|---|---|
| Call Date | `MM/DD/YYYY` |
| Call Time (CT) | `HH:MM:SS`, local time at the carrier's switch in Central Time (US Central, observing daylight saving time) |
| Calling Number | 10-digit calling party |
| Called Number | 10-digit called party |
| MO/MT | `MO` mobile originated (the requested number placed it), `MT` mobile terminated (the requested number received it) |
| Seconds | Usage seconds. Messages show `0`. May be blank when not rated. |
| Call Type | Usage type, below |

| Call Type | Meaning |
|---|---|
| V | Voice |
| S | Short message (no content provided) |
| VM | Voice mail deposit or retrieval leg |
| FW | Forwarded leg: an incoming call redirected by the network to the line's forwarding destination |

Usage records reflect network activity for the number. They do not identify the user of the
device.
