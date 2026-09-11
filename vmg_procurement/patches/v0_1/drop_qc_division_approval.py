# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt

import frappe

WORKFLOW_NAME = "VMG Quotation Comparison Approval"
DROPPED_STATE = "Pending Division Approval"
FIRST_APPROVAL = "Pending CFO Approval"
DOCTYPE = "VMG Quotation Comparison"


def execute():
	"""A quotation comparison is approved by the CFO and then the GM, nothing else.

	The original chain sent it to the Division Manager first. That is not the
	client's process, and it also disagreed with the Local Purchase Order
	workflow this comparison feeds, which already runs CFO then GM.

	Drop the Division step, point Submit straight at the CFO, and move anything
	parked on the Division Manager on to the CFO so it is not stranded without a
	valid action. The Division Manager stays an approver on VMG Purchase
	Requisition, so the Workflow State record itself is left alone.
	"""
	if not frappe.db.exists("Workflow", WORKFLOW_NAME):
		return

	workflow = frappe.get_doc("Workflow", WORKFLOW_NAME)
	if not any(s.state == DROPPED_STATE for s in workflow.states):
		return  # already migrated

	# Submit now lands on the CFO instead of the Division Manager
	for transition in workflow.transitions:
		if transition.state == "Draft" and transition.next_state == DROPPED_STATE:
			transition.next_state = FIRST_APPROVAL

	# Workflow.validate_docstatus rejects a transition whose state is missing,
	# so the transitions and the state have to go in the same save.
	workflow.set(
		"transitions",
		[t for t in workflow.transitions if t.state != DROPPED_STATE],
	)
	workflow.set("states", [s for s in workflow.states if s.state != DROPPED_STATE])
	workflow.save(ignore_permissions=True)

	stranded = frappe.get_all(DOCTYPE, filters={"workflow_state": DROPPED_STATE}, pluck="name")
	for name in stranded:
		frappe.db.set_value(
			DOCTYPE, name, "workflow_state", FIRST_APPROVAL, update_modified=False
		)

	frappe.db.commit()
	frappe.clear_cache(doctype=DOCTYPE)

	if stranded:
		print(f"  moved to {FIRST_APPROVAL}: {', '.join(stranded)}")
