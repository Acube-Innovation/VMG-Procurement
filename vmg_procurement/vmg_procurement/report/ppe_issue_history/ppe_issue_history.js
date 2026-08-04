// Copyright (c) 2026, VMG and contributors
// For license information, please see license.txt

frappe.query_reports["PPE Issue History"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -24),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "employee",
			label: __("Employee"),
			fieldtype: "Link",
			options: "Employee",
		},
		{
			fieldname: "item_type",
			label: __("Item Type"),
			fieldtype: "Select",
			options: "\nUniform Shirt\nUniform Trouser\nCoverall\nSafety Shoes\nSafety Helmet\nSafety Glasses\nGloves\nHigh Visibility Vest\nOther",
		},
		{
			fieldname: "division",
			label: __("Division"),
			fieldtype: "Link",
			options: "VMG Division",
		},
	],
};
