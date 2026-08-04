# VMG Procurement — User Guide

How procurement is done in ERPNext with the `vmg_procurement` app.
Everything starts from the **VMG Procurement workspace** (search "VMG
Procurement" in the desk). The number cards on top are the daily to-do:
Open Requisitions, LPOs Pending Approval, Orders Pending Receipt,
Invoices Outstanding, Active Project Budgets.

There is **no inventory** in this cycle: materials and services never touch
the stock ledger. Only fixed assets go through core ERPNext stock documents.

---

## The cycle at a glance

```
Site needs something
   |
   v
1. VMG Purchase Requisition (F01)  ...approved by Division Manager -> CFO -> GM
   |
   +--> Asset type? -------> core Material Request -> PO -> Receipt -> ASSETS -> Purchase Invoice
   |
   +--> Urgent? (Procurement Manager only) --> direct VMG Local Purchase Order
   |
   v
2. VMG Request for Quotation  ...enquiry emailed/printed to suppliers
   v
3. VMG Supplier Quotation  ...one per supplier, original quote attached
   v
4. VMG Quotation Comparison (F02)  ...approved by Division Manager -> CFO -> GM
   v
5. VMG Local Purchase Order (F04)  ...approved by CFO -> GM, then Send to Supplier
   v
6. VMG Purchase Receipt (GRN)  ...site receives, Procurement approves the signed delivery note
   v
7. VMG Supplier Invoice  ...Procurement verifies -> Accounts approves -> Journal Entry posts
   v
8. Payment Entry  ...Create Payment button, invoice becomes Partly Paid / Paid
```

Budget checks fire at steps 1, 5 and 8 when the document carries a project
with an active **VMG Project Budget**.

---

## Step by step

### 1. Raise a requisition (any site user)

Workspace -> **VMG Purchase Requisition** -> New.

- Pick the **Division** — it drives the number (PR-VLV-2026-00001) and fills
  cost center, project, site engineer and division manager automatically.
- Add item lines: a plain **description, qty and unit** is enough — item
  codes are optional because most purchases are non-stock.
- **Offline or emergency?** Set Source = Procurement Offline or tick
  Is Emergency: the signed copy / email / WhatsApp screenshot attachment
  becomes mandatory, and the form shows a red Emergency banner.
- **Asset purchase?** Set Requisition Type = Asset and use a fixed-asset
  item code — the system will only let it into the core asset chain.
- Save, then **Submit**. Approval runs Division Manager -> CFO -> GM; each
  approver gets an email and uses the Approve / Reject buttons. Rejection
  requires a reason. The Approval Log section records who approved when.

### 2. Route the approved requisition (procurement)

On an Approved requisition a **Create** menu appears:

- **Request for Quotation** — the normal path for materials and services.
- **Material Request** — only offered for Asset requisitions (core chain).
- **Local Purchase Order** — direct order, visible only to the
  VMG Procurement Manager, for urgent cases; a justification is mandatory.

### 3. Request for Quotation

- Items copy from the requisition. Add supplier rows — the system warns if a
  supplier is not on the **Approved Supplier List** and records it in the row.
- **The 3-quote rule** (from VMG Procurement Settings): above AED 1,000 at
  least 3 suppliers are required; below 1,000, 3 suppliers only when the
  requisition is flagged *new product or service*. The threshold note on the
  form explains which rule applies; enforcement is Warn or Stop per settings.
- Submit, then **Send Enquiry**: every supplier with an email gets the
  rate-free enquiry PDF; the rest are listed for manual printing. Status
  moves to *Sent to Suppliers*.

### 4. Supplier quotations

**Create -> Enter Supplier Quotation** on the RFQ, one per supplier.
Attach the **original quotation** (mandatory), enter rates, validity,
delivery and payment terms. Totals compute with 5% VAT and amount in words.
On submit the RFQ row ticks *Quotation Received*; duplicates per supplier
are blocked; quotations expire automatically after their validity date.

### 5. Quotation comparison (VMG-PRO-F02)

Once 2+ quotations are in, the RFQ shows **Create -> Create Comparison**.

- Click **Get Quotations**: suppliers land side by side (max 5 columns) with
  each line's rates compared and the lowest marked.
- Pick the **Selected Quotation** and a **Selection Basis**. If the choice is
  not the lowest price, or the supplier is unapproved, a **Justification** is
  mandatory — this prints on the F02 sheet.
- Submit -> approval Division Manager -> CFO -> GM. On approval the losing
  quotations become *Not Selected*, the winner *Selected*.
- Print: the landscape **Quotation Comparison Sheet VMG-PRO-F02**, one page.

**Splitting the award between suppliers.** When different lines are cheaper
from different suppliers, set **Award Mode = Split by Item** instead of
picking one quotation:

- In the Items grid, type the supplier's column number into **Award Col** on
  each line (the supplier name fills in beside it), or click **Award Lowest
  to Each Line** to award every line to its cheapest column in one go.
- Every line must be awarded before submitting; a **Justification** is
  required if any line is not awarded to its lowest rate.
- All suppliers holding an awarded line become *Selected*; the F02 sheet's
  Choice/Decision box prints the item-wise split.
- After approval, **Create -> Local Purchase Order** opens a picker: choose
  an awarded supplier and an LPO is drafted with *only their lines* (any
  quotation-level discount is prorated). Repeat for each awarded supplier —
  the comparison shows **Partially Ordered** until every awarded supplier has
  a submitted LPO, then **Ordered**. Two LPOs against the same quotation of
  one comparison are blocked.

### 6. Local Purchase Order (VMG-PRO-F04)

Three ways to create one:

- **From Comparison** (normal): Create -> Local Purchase Order on the
  approved comparison — supplier, items and rates arrive prefilled.
- **Direct Order** (urgent, Procurement Manager only): justification
  mandatory; an unapproved supplier needs a second justification. These are
  flagged DIRECT ORDER in the approval emails and appear in the audit report.
- **Repeat Order**: *Get Items from Previous Order* copies a previous LPO of
  the same supplier; *Duplicate* clones the current one.

Before submit the policy fields must be complete: delivery + invoicing
address, required delivery date (or service visit date, with week number),
project or job number, and terms (defaulted from settings). Approval runs
**CFO -> GM**; on approval the status becomes **To Receive** and the
**Send to Supplier** button emails the F04 PDF and stamps who sent it when.

### 7. Goods receipt (GRN)

Site receives goods against the supplier's delivery note:

- New **VMG Purchase Receipt** -> pick the LPO -> **Get Items from Local
  Purchase Order** (only pending lines load; partial deliveries are normal —
  the next receipt offers only what is still pending).
- Enter received vs **accepted** quantities; any rejection demands a reason.
  Over-receipt beyond the tolerance in settings is blocked.
- Attach the **signed delivery note** (mandatory), submit — the Procurement
  Department approves or rejects it. On approval the receipt is **To Bill**
  and the LPO shows Partially / Fully Received with percentages.

### 8. Supplier invoice and posting

- On the approved receipt: **Create -> Supplier Invoice**. Quantities arrive
  at accepted levels. Attach the **original invoice**; the supplier invoice
  number is checked for duplicates.
- **Three-way match**: invoice rate/qty vs ordered rate and accepted qty,
  with tolerances and Warn/Stop behaviour from settings.
- Approval: **Procurement verifies -> Accounts approves**. Only at Accounts
  approval does the system post a core **Journal Entry** (expenses by line
  with cost center and project, input VAT, credit to the supplier with due
  date) — nothing is posted before that, and cancelling the invoice reverses
  the Journal Entry.

### 9. Payment

On the approved invoice: **Create -> Payment** opens a core Payment Entry
prefilled with the outstanding amount and the journal entry referenced.
The invoice tracks **Unpaid -> Partly Paid -> Paid** straight from the
ledger, and flips to **Overdue** automatically after the due date.
An invoice cannot be cancelled while a payment stands against it.

---

## Side flows

### Fixed assets (core chain)

Asset requisition -> **Material Request** (ASSET-MR series, auto-set) ->
core **Purchase Order** (only procurement roles may create core POs; every
line must be a fixed-asset item) -> core **Purchase Receipt** -> ERPNext
creates **one Asset per unit** with its own number; the manufacturer serial
entered on the receipt line is copied to each asset -> **Purchase Invoice**.
The whole chain carries the requisition reference; see the **Asset
Procurement Register** report.

### Uniforms and PPE (F03 / F07)

- Uniform needs are raised as an ordinary **VMG Purchase Requisition** with
  **Requisition Type = Staff Uniform and PPE**. That reveals a *Staff
  Uniform Details* section: a Reason and a **Uniform Employees** table (one
  row per employee and item, with type, size and qty). The system warns when
  someone was issued the same item within the reissue period (settings,
  default 12 months).
- On save the requisition's item lines are **rebuilt automatically** from
  the employee rows (identical item + size grouped), so the normal approval
  and RFQ -> comparison -> LPO flow just works — don't edit the items table
  by hand on a uniform requisition.
- Printing a uniform requisition uses the **F03 staff uniform layout**
  (employee matrix with size/qty per Coverall, T-Shirt, Jacket, Helmet,
  Shoes) automatically; other requisition types print on F01.
- When goods arrive: **VMG PPE and Uniform Handover** -> pick the approved
  uniform requisition -> *Get Items from Requisition* -> submit (= Issued).
  Print F07, collect signatures, tick *Employee Acknowledged* per row ->
  status Acknowledged. The **PPE Issue History** report shows who is due
  replacement.

### Project budgets

**VMG Project Budget** (Project User or CFO only): per project, cost center
and fiscal year, with an amount per expense account. Once submitted it is
Active and consumption tracks automatically:

- *soft committed* = approved requisitions not yet ordered
- *firm committed* = approved LPOs not yet invoiced
- *actual* = posted invoices, straight from the ledger

Checks fire on requisition submit/approval, LPO submit/approval and payment,
behaving per settings (Ignore / Warn / Stop). A Warn that is overridden
records **who and when** on the document. See **VMG Project Budget
Utilisation** and the workspace chart.

---

## Who does what

| Role | Does |
|---|---|
| VMG Site User / Site Engineer | Raise requisitions and uniform requests, receive goods (GRN) |
| VMG Division Manager | 1st approval on requisitions, comparisons, uniform requests |
| VMG CFO | 2nd approval + 1st approval on LPOs; budgets |
| VMG General Manager | Final approval on requisitions, comparisons, LPOs |
| VMG Procurement User | RFQs, quotations, comparisons, LPOs, receipt approval, invoice verification, supplier issue |
| VMG Procurement Manager | Everything above + direct orders + core (asset) POs |
| VMG Accounts User | Invoice approval (posts the Journal Entry), payments |
| VMG Project User | Project budgets |

Site users see only their own division's documents when a **User
Permission** on VMG Division is set for them.

## Reports (workspace -> Reports card)

Purchase Order Log · VMG Supplier Outstanding · Procurement Cycle Register ·
Pending Approvals (the daily chase list) · Quotation Analysis · Order vs
Receipt vs Invoice · **Emergency and Direct Order Register** (the audit
report) · Approved Suppliers List (VMG-PRO-F05) · Asset Procurement
Register · PPE Issue History · VMG Project Budget Utilisation.

## Settings that drive behaviour

**VMG Procurement Settings** (workspace -> Setup): quote threshold (AED
1,000) and minimum supplier counts, threshold enforcement (Warn/Stop),
default terms and accounts, over-receipt tolerance, invoice matching
tolerances and action, budget actions per stage, uniform reissue period,
notification emails on/off.
