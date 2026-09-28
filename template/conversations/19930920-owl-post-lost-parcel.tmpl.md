<!--
Example conversation. Delete this file after storing the first real one.
Replace the placeholder participants and messages in copied conversations.
The `related` entry points at a conversation not included in this example.
-->
---
title: Lost parcel sent by owl post
context: >
  Kept because the carrier first denied the handover, and the signed slip is
  the only evidence the parcel was ever accepted. Needed if the claim is
  disputed again. The closing reply arrived undated; 30 September is the
  nearest date the thread supports.
description: >
  A group thread with the carrier about a parcel that never arrived. Support
  denies any acceptance record, a second sender confirms the handover, and the
  carrier then opens a claim and traces the parcel to a mis-sorting.
participants:
  - id: h-granger
    name: Hermione Granger
    email: h.granger@example.org
  - id: owl-post-support
    name: International Owl Post, support desk
    email: support@example.com
  - id: m-mcgonagall
    name: Minerva McGonagall
related:
  - 19931102-owl-post-compensation
---

## @h-granger [1993-09-20T18:40:00+01:00]

I am writing about a parcel handed to your office on 13 September. It has not
arrived and the tracking feather has stopped updating.

The parcel contained one book and a copy of the handover slip [document].

## @owl-post-support [1993-09-21T09:05:00+01:00]

Thank you for your message. Our records show no parcel accepted under your
name on that date. Without an acceptance record we cannot open a claim.

## @h-granger [1993-09-21T19:12:00+01:00]

The parcel was handed over by a member of staff on my behalf, which is
probably why my name is not on the record. I have asked her to confirm.

## @m-mcgonagall [1993-09-22T08:30:00+01:00]

I handed the parcel to your Hogsmeade office myself on 13 September and
received a signed slip. It carries reference HG-1993-0913.

> @owl-post-support [1993-09-21T09:05:00+01:00]
> Our records show no parcel accepted under your name on that date.

The record exists under my name, not Miss Granger's.

## @owl-post-support [1993-09-22T15:47:00+01:00] [edited]

We have located the acceptance record and opened claim 4417.

The parcel was mis-sorted at the Hogsmeade hub. We expect to confirm its
location within five working days.

## @h-granger [1993-09-23T17:05:00+01:00]

Noted. Please send the outcome in writing once the parcel is traced.

For the record, the tracking page showed this before it stopped updating:

```text
## status
in transit, Hogsmeade hub
```

## @owl-post-support [1993-09-23T18:02:00+01:00]

Understood. Our tracking template prints the field name on its own line:

\## status

That heading comes from the template and is not part of the parcel record.

## @m-mcgonagall [1993-09-24T11:20:00+01:00]

For the compensation form the carrier asked for the school vault number. I
gave it to them by floo, not in writing: [secret].

## @owl-post-support [1993-09-30T09:00:00+01:00] [approximate]

The parcel has been found and is being returned to the Hogsmeade office.
Compensation is handled separately; see the follow-up thread.

The original slip photographed at intake is attached.

[photo1] [photo2] [photo3]
