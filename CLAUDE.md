# vmg_procurement — VMG Procurement System

ERPNext v15 custom app implementing the complete VMG procurement cycle.
App: `vmg_procurement` · Module: `VMG Procurement` · Site: `vmg`

## Business Context

- VMG does NOT maintain inventory for materials and services. No stock entries,
  no bins, no stock ledger for the normal purchase cycle.
- Only FIXED ASSETS are received into inventory and tracked with serial numbers.
- Therefore the whole purchase cycle is rebuilt as CUSTOM DocTypes, mirroring
  the core purchase documents but without any stock behaviour.
- Fixed asset procurement uses the CORE ERPNext DocTypes as they are.
- The Purchase Requisition is COMMON to both branches and is a custom DocType.
- Divisions ARE cost centers: every VMG Division is linked 1:1 to a leaf Cost
  Center via its `cost_center` field (reused if a leaf with the same name
  exists, otherwise auto-created under the company root on first save).
  Documents in later steps derive their cost center from the selected division.

## Target Architecture

Custom chain (no inventory):

```
VMG Purchase Requisition -> VMG Request for Quotation -> VMG Supplier Quotation
  -> VMG Quotation Comparison -> VMG Local Purchase Order -> VMG Purchase Receipt
  -> VMG Supplier Invoice -> core Journal Entry -> core Payment Entry
```

Asset chain (with inventory):

```
VMG Purchase Requisition -> core Material Request (Purchase) -> core Supplier Quotation
  -> core Purchase Order -> core Purchase Receipt -> core Purchase Invoice -> core Asset
```

Supporting DocTypes: VMG Procurement Settings (Single), VMG Division,
VMG PPE Handover, VMG Project Budget. (VMG Staff Uniform Request was REMOVED
post-build: uniform requests are now VMG Purchase Requisitions of type
"Staff Uniform and PPE" carrying a `uniform_employees` child table (VMG
Uniform Request Item); the PR rebuilds its items from those rows on save,
PPE handovers link the requisition via `purchase_requisition`, and the F03
print format lives on VMG Purchase Requisition — the PR form JS defaults the
print format by requisition_type: F03 for uniform, F01 otherwise. Migration:
patches/v0_1/merge_uniform_requests_into_requisitions.py.)

## Mandatory Rules for Every Step

1. All code, DocTypes, print formats, workflows and fixtures live inside this
   app (`vmg_procurement`), under the single module `VMG Procurement`.
2. Never edit core DocTypes or core Python files. Extend core only through
   Custom Field, Property Setter, Client Script, Server Script or
   hooks.py `doc_events`.
3. Custom DocType names are always prefixed with `VMG`.
4. No custom DocType may create Stock Ledger Entries or Bin records.
5. Currency is AED. Company default currency and settings drive all rounding.
6. Every DocType that carries a value must expose **project**, **cost center**
   and **division** for budget and reporting.
7. Export every DocType, workflow, role, print format and custom field as
   fixtures in hooks.py so the whole build is version controlled and portable.
8. After each step, run `bench --site vmg migrate` and report exactly which
   files were created or changed and how to test the step manually.
9. Do not implement anything that belongs to a later step. Stop when the step
   is complete.

## Client Forms Reference

Source: `/home/acubeadmin/Projects/vmg/Documents/Fw_ Procurement process (Current)`.
Later steps MUST follow these forms, not invented layouts.

- **Process rules** (Procurement Process.docx): PR must carry contract ref /
  cost center / dept, qty, full description, desired delivery date, proposed
  supplier and any quotations. PRs are approved by the **Division Manager /
  Site Engineer**. Above AED 1,000 -> min 3 supplier inquiries; below 1,000 ->
  3 quotes only for NEW products/services. Suppliers come from the Approved
  Supplier List (F05). All orders go out as LPOs, uniquely numbered, approved
  by **CFO and General Manager**; urgent purchases may use non-approved
  suppliers. Delivery Note signed by recipient -> Procurement verifies invoice
  (invoice + LPO copy + DO copy), posts to a **Purchase Order Log**, then
  Finance pays.
- **F01 Purchase Requisition** (print): Date, PR No, Site/Division,
  Department, item rows (Item#, Description, Quantity, Unit - no prices),
  Requested By + Approved By signatures, "For Office Use Only" box (Remarks,
  Procurement signature, Date), footer "White Copy - Procurement, Blue Copy -
  Requester".
- **F02 Quotation Comparison** (step 07): header PR No, Date, Site; up to 3
  supplier columns each with Company Name / Contact Person / Contact Detail
  and per-item Cost + Total; footer rows Sub Total, Discount, Net Amount,
  VAT (5%), TOTAL (AED); extra fields: quoted at tender stage (price),
  supplier quote ref, supplier quote date, expected delivery (weeks from
  order); Recommendations (Procurement) and Choice/Decision (Operations:
  Division Manager / General Manager).
- **F03 Staff Uniform Request** (step 15): Department/Site, Date; rows per
  employee (Name, Designation) with Size+Qty pairs for Coverall, T-Shirt,
  Jacket, Helmet, Shoes; Requested By / Approved By signatures.
- **F04 Local Purchase Order** (steps 09-10, print): company TRN; supplier
  block (name, PO Box, tel, fax/email, attn); LPO No, Date, Req. No, Quote
  Ref + Date; line items (S.No, Description, Qty, Unit, Unit Price AED,
  Total AED); Sub Total, Discount, Net Amount, VAT (5%), Grand Total; amount
  in words; Payment Terms, Delivery To, Project Name, Other Terms (default:
  "Order Acknowledgement to be done within 48 hours, otherwise it will be
  considered as accepted."); signatures Initiated-Procurement / Finance /
  Approved By. Mandatory info: order no+date, project/job number, delivery
  address, invoicing address, required delivery / service visit date (week
  numbers).
- **F05 Approved Supplier List**: Sl No, Supplier Name, Address, Contact
  Person, Contact No., Email ID, Item/Materials (free text, e.g. "Hardware
  Items" -> custom field `vmg_items_materials`), Remarks.
- **F07 PPE & Uniform Hand Over** (step 15): Name, Designation, HO Ref#,
  Date; item rows (Sl#, Description, Quantity, Remarks); signatures Employee /
  HR-Admin / Dept. Head. Issued by site in charge on receipt of uniform/safety
  items, forwarded to Procurement.

## Chain Conventions (fixed in step 04 — later steps MUST match)

- Custom chain DocTypes (VMG RFQ, VMG LPO, ...) link back to the requisition
  via a `purchase_requisition` (Link) header field and a `requisition_item`
  (Data) field on their item rows. Core doctypes use custom fields
  `vmg_purchase_requisition` / `vmg_division` (header) and
  `vmg_requisition_item` (item rows).
- VMG RFQ / LPO headers must carry `division`, `project`, `cost_center` and
  items must use `description`, `qty`, `uom` so get_mapped_doc auto-copies.
- VMG Local Purchase Order (built in step 09): three routes tracked by
  `order_route` (From Comparison / Direct Order / Repeat Order) and
  `is_direct_order` (Check) - this superseded the earlier `comparison_skipped`
  plan. Direct orders are restricted to VMG Procurement Manager server-side
  and demand `direct_order_justification`; unapproved suppliers are allowed
  only on Direct Order (or an approved comparison, whose justification is
  copied) and demand `non_approved_supplier_justification`. Items carry
  `expense_account` (default from settings), received/billed/pending qty for
  steps 12-13. update_requisition_ordered_qty() keeps PR items in sync;
  routing distinguishes "Ordered" vs "Partially Ordered". LPO submit sets
  QC status "Ordered" (reverted on cancel). Step 10 DONE: CFO->GM workflow
  (Approved -> status "To Receive"), F04 print, Send to Supplier
  (send_to_supplier(), stamps sent_to_supplier_on/sent_by, Communication on
  the timeline), Purchase Order Log report, and `notification_flags` (hidden,
  computed) prefixing DIRECT ORDER / NON APPROVED SUPPLIER into workflow
  notification subjects (the 140-char subject field cannot hold the jinja).
- Step 12 DONE (VMG Purchase Receipt, GRN-*): links via `local_purchase_order`;
  get_items_from_lpo pulls pending lines only; over-receipt capped by settings
  over_receipt_tolerance_percent; update_lpo_receipt_status() recomputes LPO
  item received/pending, per_received and To Receive / Partially Received /
  Fully Received (accepted qty counts as received; rejected goods stay
  pending); workflow "VMG Purchase Receipt Approval" (Pending Procurement
  Approval state) sets status To Bill on Approved. No stock ledger anywhere.
- Step 13 DONE (VMG Supplier Invoice, SINV-*): posts a core Journal Entry
  (never GL Entry directly) when the workflow reaches Approved - idempotent
  via the journal_entry field; expense debits are prorated by net/total so a
  header discount still balances; the JE carries due_date so payable ageing
  works; outstanding_amount always recomputed FROM GL Entry (voucher_no or
  against_voucher = the JE). Payment Entry hooks + a daily job maintain
  Unpaid/Partly Paid/Paid/Overdue. update_billing_status() maintains receipt
  per_billed/Billed and LPO billed_qty/per_billed/Completed. Cancellation:
  payments must be cancelled first; the JE is cancelled before the invoice
  (posting_status Reversed).
- Step 14 (payments and logs) conventions: pay VMG Supplier Invoices through
  core Payment Entry rows referencing the invoice's Journal Entry
  (reference_doctype "Journal Entry") - on_payment_entry_change already
  refreshes invoice status/outstanding for exactly that shape. Client still
  owes: real Input VAT account (settings currently points at "Excise 100% -
  VMG" picked by tests) and a proper Default Expense Account.
- VMG Supplier Quotation (step 06) must link back via `request_for_quotation`
  (Link) + `supplier` (Link Supplier); its items via `rfq_item` (Data) and
  `requisition_item` (Data). On submit it must set `quotation_received` /
  `supplier_quotation` on the matching VMG RFQ Supplier row and call
  vmg_request_for_quotation.update_status_from_quotations(). Step 06 also
  upgrades VMG RFQ Supplier.supplier_quotation from Data to Link.
- VMG Quotation Comparison (step 07, built): links via `request_for_quotation`;
  on submit sets status "Pending Approval", stamps Selected / Not Selected on
  the quotations and sets the RFQ to "Comparison Created" (all reversed on
  cancel). Step 08 must: add the approval workflow on its hidden
  `workflow_state` field (statuses Pending Approval/Approved/Rejected exist),
  and build the landscape VMG-PRO-F02 print format over the fixed columns
  rate_1..rate_5 / amount_1..amount_5 of VMG Comparison Item (render a dash
  where a rate is NULL: that supplier did not quote the line; supplier
  column headers come from the VMG Comparison Supplier rows by column_no).
  DONE in step 08. Landscape print format gotcha for future formats: frappe's
  print_format.css sets body min-height 297mm + 2rem margins under
  @media screen (which wkhtmltopdf uses) - a landscape format MUST override
  `body { min-height: 0 !important; margin: 0 auto !important; }` or every
  PDF grows an empty second page. Orientation is set via
  `.print-format { orientation: Landscape; }` in the format's own CSS.
  Also: frappe.reload_doc skips files whose `modified` is older than the DB
  record (imports stamp real time) - pass force=True when re-importing a
  tweaked print format in the same day.
- Step 09 LPO from an Approved comparison: qc_mod.make_local_purchase_order
  maps `quotation_comparison`, `purchase_requisition`, `supplier` (selected)
  and `supplier_quotation` (selected) onto the LPO; server enforces
  workflow_state == Approved. QC status must move to "Ordered" when the LPO
  is submitted.
- Split awards (added post-build, modelled on visa_profession_management's
  Comparative Statement): QC `award_mode` Select (Single Supplier / Split by
  Item). Split mode: VMG Comparison Item carries editable `awarded_column`
  (+ read-only `awarded_supplier`); sync_item_awards() validates the column
  quoted the line, flags every awarded supplier row is_selected, clears
  selected_supplier/quotation and totals awarded_value (net). Submit demands
  every line awarded; justification when any line is not its lowest column.
  make_lpo_from_comparison(source, supplier_quotation=...) builds one LPO per
  awarded quotation with only that supplier's lines (matched back by
  description then rate; quotation-level discount prorated by awarded share).
  LPO.validate_duplicate_comparison_order blocks a second active LPO on the
  same comparison+quotation; compute_ordered_status() drives QC status
  Approved -> Partially Ordered -> Ordered as awarded LPOs are submitted
  (status Select gained a "Partially Ordered" option). The QC form JS has an
  "Award Lowest to Each Line" helper and a supplier-picker dialog on Create ->
  Local Purchase Order. TESTING GOTCHA: don't wrap submit/cancel flows in a
  DB savepoint in console tests - something in the cancel path commits and
  releases the savepoint, so test docs persist; create test docs normally and
  delete them in reverse dependency order afterwards.
- Asset chain (step 11, built in utils/asset_chain.py): ASSET-* naming series
  pinned via Property Setters + before_insert hooks on MR/SQ/PO/PR/PI; the
  requisition trace propagates header-to-header through the items' upstream
  links; core PO creation is restricted to VMG Procurement User/Manager
  (PermissionError otherwise); PR on_submit verifies one Asset per unit,
  copies vmg_manufacturer_serial_no and stamps the trace onto the Assets.
  BEWARE the scaffolding app's PR on_submit hook (is_rented): it force-saves
  and submits EVERY asset created by ANY Purchase Receipt with
  calculate_depreciation=1, so every Asset Category used by the asset chain
  MUST have a finance_books row and items must carry rates, or PR submit
  fails. Client still owes CWIP accounts on all asset categories (run
  vmg_procurement.setup.check_asset_setup for the current gap list).
- Routing lives in `utils/routing.py`: get_allowed_targets() decides the
  chain (Asset -> core Material Request; else VMG RFQ, plus direct VMG LPO
  for role VMG Procurement Manager); update_requisition_status() recomputes
  requisition status (MR/RFQ submitted -> "RFQ Created", LPO/PO submitted ->
  "Ordered", reverts to "Approved" on cancellation); doc_events for VMG RFQ /
  VMG LPO are already registered in hooks.py.

## Build Plan

- [x] 01 setup and masters
- [x] 02 purchase requisition
- [x] 03 requisition workflow
- [x] 04 requisition routing
- [x] 05 request for quotation
- [x] 06 supplier quotation
- [x] 07 quotation comparison
- [x] 08 comparison approval and print
- [x] 09 local purchase order
- [x] 10 LPO workflow and print
- [x] 11 asset chain on core DocTypes
- [x] 12 purchase receipt
- [x] 13 supplier invoice and accounting
- [x] 14 payments and logs
- [x] 15 uniform and PPE
- [x] 16 project budget

Tick a step only when it is migrated and manually tested on site `vmg`.
BUILD COMPLETE: all 16 steps migrated and tested. Field gotcha discovered in
step 16: an editable field with `fetch_from` and WITHOUT `fetch_if_empty` is
clobbered server-side by the fetched value on every save - always set
fetch_if_empty on user-editable fetch fields (fixed on PR/SUR/PPE `project`).
