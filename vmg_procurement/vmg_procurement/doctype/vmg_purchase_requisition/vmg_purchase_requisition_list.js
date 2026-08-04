// Copyright (c) 2026, VMG and contributors
// For license information, please see license.txt

frappe.listview_settings["VMG Purchase Requisition"] = {
	add_fields: ["workflow_state", "status", "is_emergency"],

	get_indicator(doc) {
		const colours = {
			"Draft": "red",
			"Pending Division Approval": "orange",
			"Pending CFO Approval": "orange",
			"Pending GM Approval": "orange",
			"Approved": "green",
			"Rejected": "red",
		};
		const state = doc.workflow_state;
		if (state && colours[state]) {
			return [__(state), colours[state], "workflow_state,=," + state];
		}
	},
};
