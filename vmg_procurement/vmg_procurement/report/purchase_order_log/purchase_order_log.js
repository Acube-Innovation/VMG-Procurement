// Copyright (c) 2026, VMG and contributors
// For license information, please see license.txt

frappe.query_reports["Purchase Order Log"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "division",
			label: __("Division"),
			fieldtype: "Link",
			options: "VMG Division",
		},
		{
			fieldname: "supplier",
			label: __("Supplier"),
			fieldtype: "Link",
			options: "Supplier",
		},
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options:
				"\nDraft\nPending Approval\nApproved\nRejected\nTo Receive\nPartially Received\nFully Received\nTo Bill\nCompleted\nClosed\nCancelled",
		},
	],
};
