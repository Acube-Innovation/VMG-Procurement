# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt

import frappe

WORKFLOW_NAME = "VMG Purchase Receipt Approval"
DROPPED_STATE = "Pending Procurement Approval"
FINAL_STATE = "Approved"
DOCTYPE = "VMG Purchase Receipt"


def execute():
	"""A goods receipt does not need procurement approval.

	Receiving is a record of what physically arrived, not a decision, so
	submitting a receipt now takes it straight to Approved and it is ready to
	bill. The workflow is kept rather than removed: `make_supplier_invoice`
	gates on `workflow_state == "Approved"`, so a receipt with no workflow state
	at all could never be billed.

	Whether goods were accepted is still recorded per receipt on
	`acceptance_status` (Pending / Accepted / Partially Accepted / Rejected),
	which is separate from this approval chain.
	"""
	if not frappe.db.exists("Workflow", WORKFLOW_NAME):
		return

	workflow = frappe.get_doc("Workflow", WORKFLOW_NAME)
	if not any(s.state == DROPPED_STATE for s in workflow.states):
		return  # already migrated

	# Submitting now lands directly on Approved. There are two Draft rows, one
	# per submitting role (VMG Site User and VMG Procurement User).
	for transition in workflow.transitions:
		if transition.state == "Draft" and transition.next_state == DROPPED_STATE:
			transition.next_state = FINAL_STATE

	# Workflow.validate_docstatus rejects a transition whose state is missing,
	# so the transitions and the state have to go in the same save.
	workflow.set(
		"transitions",
		[t for t in workflow.transitions if t.state != DROPPED_STATE],
	)
	workflow.set("states", [s for s in workflow.states if s.state != DROPPED_STATE])
	workflow.save(ignore_permissions=True)

	# anything waiting on procurement is already received, so it is approved
	stranded = frappe.get_all(DOCTYPE, filters={"workflow_state": DROPPED_STATE}, pluck="name")
	for name in stranded:
		frappe.db.set_value(
			DOCTYPE,
			name,
			{"workflow_state": FINAL_STATE, "status": "To Bill"},
			update_modified=False,
		)

	frappe.db.commit()
	frappe.clear_cache(doctype=DOCTYPE)

	if stranded:
		print(f"  moved to {FINAL_STATE} / To Bill: {', '.join(stranded)}")
