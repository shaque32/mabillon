# Accounts: rulings needed (fix/accounts, 2026-11-10)

No frozen file needs a change for this branch. These are judgment calls on how to read claim
wording. The conservative reading is what the code does now.

## A1. Which apps are "a text message" (implemented conservatively; please confirm)

`_text_message_account` reads a number the model wrote on no app ("unknown", "SMS", "text"), in
a claim about a text message, on the phone's own messaging app. The candidates are the apps
whose records are a phone's own messages: the phone-number apps of `checks/_common._TEL_APPS`
(SMS, MMS, iMessage, RCS, Phone) and the wider apps of `WIDER_APPS` (an export's "Native
Messages", which holds iMessages and SMS). Only those that hold a message thread in the case
count, so an "MMS" or "Phone" app with accounts but no threads (the Android 12 package) is not
a second candidate. Exactly one must be left, or nothing is read.

The trigger words are "SMS", "MMS", "text message(s)", "texted" and "texting". "Text" alone is
not one ("the text of the message"). A claim that also names a call is left as written.

Options:
- (a) As implemented. An export that splits "SMS" and "iMessage" into two apps gets no reading
  (refused, the claim stays untested). A case whose only phone message app is "iMessage" reads
  "text message" there.
- (b) Like (a), but "text message" never reads an app named only "iMessage": an iMessage is not
  an SMS, though people call both texts.
- (c) Like (a), but with two candidates both are searched as one party (SMS and iMessage).
  Not recommended: a party on two apps is a merge of accounts the records keep apart.

Recommendation: (a). It never picks among apps, and the iOS "Native Messages" note already
tells the reader that app holds iMessages and SMS together.

## A2. Bare digits against a number written with "+" (iOS 15 B12): left refused

B12 writes the Telegram contact's number as "19198887386". The case's Telegram accounts write it
"+1 919 888 7386" and "+1 919-888-7386", so the account is there under another spelling.
`phone_digits` does not read digits run together with no "+", because their country is not
written.

The WhatsApp reading in this branch (`_jid_number`) is different: a WhatsApp id writes the number
as bare digits by definition, so "19195794674" is exactly the id's number, with no country to
guess. A "+" identifier is a guess: "9198887386" (a US number written without its 1) has the
same digits as "+91 98887386" (India).

Options:
- (a) Keep refused. Recommended.
- (b) Read bare digits of 11 to 15 digits as the "+" number with exactly those digits on the app
  the claim names, never 10 or fewer. Even then a national number (an 11-digit Chinese mobile,
  "138...") can equal another country's international digits.

Even under (b), B12 would still not be tested well, for two reasons:
- `contact_entry` takes the number as one account and refuses two (`_accounts` with
  `one_number=False` accepts only one account holding the number). Telegram holds the number
  twice, as two spellings.
- `ContactCheck` does not know which app a contact is for: the contacts table has no app
  column. "Saved in the TARGET PHONE's Telegram contacts" would pass on a contact of that name
  and number saved by any app.

## A3. A contact entry whose number no account on the named app holds (iOS 15 B15): left refused

The GroupMe contact's number "+1 919-888-7386" is only in the contacts table. No GroupMe account
holds it, so the refusal is correct. A fix would need two frozen-file changes:
- `contact_entry` taking the number as written instead of an account (`core/contracts.py` and
  the template);
- contacts that record their app (`core/schema.sql`).

Not proposed now.

## A4. A non-number identifier on no named app (iOS 15 B34): left refused

"HE4RT9WW" is held by exactly one account in the case, on the export's "Unspecified App Call".
The claim names no app. Reading it would let an identifier pick the app, with the same risk as
a name picking it: the claim's four calls would be counted on whichever app holds the id.

Recommendation: keep refused. R1 reads the call log only by phone number.
