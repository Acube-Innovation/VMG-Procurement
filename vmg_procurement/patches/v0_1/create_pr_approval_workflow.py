# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt

import frappe

STATES = [
	("Draft", "Danger"),
	("Pending Division Approval", "Warning"),
	("Pending CFO Approval", "Warning"),
	("Pending GM Approval", "Warning"),
	("Approved", "Success"),
	("Rejected", "Danger"),
]

ACTIONS = ["Submit", "Approve", "Reject"]

WORKFLOW_NAME = "VMG Purchase Requisition Approval"


def execute():
	"""Create the workflow states, actions and the PR approval workflow.

	Insert-only for existing records: shared Workflow States (Draft, Approved,
	Rejected, ...) are reused and only get a style if they have none, so other
	apps' workflows on this bench are not restyled."""
	for name, style in STATES:
		if frappe.db.exists("Workflow State", name):
			if not frappe.db.get_value("Workflow State", name, "style"):
				frappe.db.set_value("Workflow State", name, "style", style)
		else:
			frappe.get_doc(
				{"doctype": "Workflow State", "workflow_state_name": name, "style": style}
			).insert(ignore_permissions=True)

	for action in ACTIONS:
		if not frappe.db.exists("Workflow Action Master", action):
			frappe.get_doc(
				{"doctype": "Workflow Action Master", "workflow_action_name": action}
			).insert(ignore_permissions=True)

	if frappe.db.exists("Workflow", WORKFLOW_NAME):
		return

	frappe.get_doc(
		{
			"doctype": "Workflow",
			"workflow_name": WORKFLOW_NAME,
			"document_type": "VMG Purchase Requisition",
			"workflow_state_field": "workflow_state",
			"is_active": 1,
			"send_email_alert": 1,
			"states": [
				{"state": "Draft", "doc_status": "0", "allow_edit": "VMG Site User"},
				{"state": "Draft", "doc_status": "0", "allow_edit": "VMG Procurement User"},
				{
					"state": "Pending Division Approval",
					"doc_status": "1",
					"allow_edit": "VMG Division Manager",
				},
				{"state": "Pending CFO Approval", "doc_status": "1", "allow_edit": "VMG CFO"},
				{
					"state": "Pending GM Approval",
					"doc_status": "1",
					"allow_edit": "VMG General Manager",
				},
				{"state": "Approved", "doc_status": "1", "allow_edit": "VMG Procurement User"},
				{"state": "Rejected", "doc_status": "1", "allow_edit": "VMG Procurement User"},
			],
			"transitions": [
				{
					"state": "Draft",
					"action": "Submit",
					"next_state": "Pending Division Approval",
					"allowed": "VMG Site User",
					"allow_self_approval": 1,
				},
				{
					"state": "Draft",
					"action": "Submit",
					"next_state": "Pending Division Approval",
					"allowed": "VMG Procurement User",
					"allow_self_approval": 1,
				},
				{
					"state": "Pending Division Approval",
					"action": "Approve",
					"next_state": "Pending CFO Approval",
					"allowed": "VMG Division Manager",
					"allow_self_approval": 1,
				},
				{
					"state": "Pending Division Approval",
					"action": "Reject",
					"next_state": "Rejected",
					"allowed": "VMG Division Manager",
					"allow_self_approval": 1,
				},
				{
					"state": "Pending CFO Approval",
					"action": "Approve",
					"next_state": "Pending GM Approval",
					"allowed": "VMG CFO",
					"allow_self_approval": 1,
				},
				{
					"state": "Pending CFO Approval",
					"action": "Reject",
					"next_state": "Rejected",
					"allowed": "VMG CFO",
					"allow_self_approval": 1,
				},
				{
					"state": "Pending GM Approval",
					"action": "Approve",
					"next_state": "Approved",
					"allowed": "VMG General Manager",
					"allow_self_approval": 1,
				},
				{
					"state": "Pending GM Approval",
					"action": "Reject",
					"next_state": "Rejected",
					"allowed": "VMG General Manager",
					"allow_self_approval": 1,
				},
			],
		}
	).insert(ignore_permissions=True)
