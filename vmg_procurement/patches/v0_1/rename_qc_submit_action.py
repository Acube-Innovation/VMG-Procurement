# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt

import frappe

WORKFLOW_NAME = "VMG Quotation Comparison Approval"
OLD_ACTION = "Submit"
NEW_ACTION = "Forward to CFO"


def execute():
	"""Label the first step for what it actually is.

	A procurement user leaving a comparison does not "approve" anything, they
	hand it to the CFO, so the button on a draft reads "Forward to CFO". Only
	the CFO and the GM approve (see drop_qc_division_approval.py).

	The action name is cosmetic to the framework: the document still submits,
	because the docstatus comes from the target state, not from the action.
	"Submit" is left in place -- the other VMG workflows still use it.
	"""
	if not frappe.db.exists("Workflow", WORKFLOW_NAME):
		return

	if not frappe.db.exists("Workflow Action Master", NEW_ACTION):
		frappe.get_doc(
			{"doctype": "Workflow Action Master", "workflow_action_name": NEW_ACTION}
		).insert(ignore_permissions=True)

	workflow = frappe.get_doc("Workflow", WORKFLOW_NAME)
	changed = False
	for transition in workflow.transitions:
		if transition.state == "Draft" and transition.action == OLD_ACTION:
			transition.action = NEW_ACTION
			changed = True

	if not changed:
		return  # already renamed

	workflow.save(ignore_permissions=True)
	frappe.db.commit()
	frappe.clear_cache(doctype="VMG Quotation Comparison")
