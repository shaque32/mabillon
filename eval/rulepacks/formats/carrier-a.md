# Carrier A: call detail records, subscriber line production

*Invented for Mabillon's synthetic evaluation. Carrier A is not a real carrier, and this guide
copies no real carrier's documentation.*

Carrier A returns call detail records for one subscriber line (the target number) as a CSV
file with one header row. The sample is `samples/carrier-a.csv`.

| Column | Meaning |
|---|---|
| Date | Date the record starts, `YYYY-MM-DD` |
| Time (UTC) | Time the record starts, `HH:MM:SS`, in Coordinated Universal Time |
| Originating | Number that originated the call or message, 10 digits |
| Terminating | Number the call or message was sent to, 10 digits |
| Direction | `OUT` if the target number originated it, `IN` if the target number received it |
| Duration (s) | Whole seconds the network held the call. Messages show `0`. May be blank. |
| Type | Record type, below |

| Type | Meaning |
|---|---|
| VOICE | A voice call between the two numbers |
| SMS | A text message event. Carrier A does not return message content. |
| VM | A call routed to the voicemail platform. Duration is the voicemail session. |
| CFWD | A call to the target number that the network forwarded onward under the line's call-forwarding setting |

All times are UTC. Carrier A does not record which handset or person used the line.
