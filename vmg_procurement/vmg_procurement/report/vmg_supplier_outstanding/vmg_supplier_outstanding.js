// Copyright (c) 2026, VMG and contributors
// For license information, please see license.txt

frappe.query_reports["VMG Supplier Outstanding"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -3),
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
			fieldname: "only_overdue",
			label: __("Only Overdue"),
			fieldtype: "Check",
		},
	],
};
