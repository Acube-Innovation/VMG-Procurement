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
VMG Staff Uniform Request, VMG PPE Handover, VMG Project Budget.

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

## Build Plan

- [x] 01 setup and masters
- [ ] 02 purchase requisition
- [ ] 03 requisition workflow
- [ ] 04 requisition routing
- [ ] 05 request for quotation
- [ ] 06 supplier quotation
- [ ] 07 quotation comparison
- [ ] 08 comparison approval and print
- [ ] 09 local purchase order
- [ ] 10 LPO workflow and print
- [ ] 11 asset chain on core DocTypes
- [ ] 12 purchase receipt
- [ ] 13 supplier invoice and accounting
- [ ] 14 payments and logs
- [ ] 15 uniform and PPE
- [ ] 16 project budget

Tick a step only when it is migrated and manually tested on site `vmg`.
