// Copyright (c) 2026, VMG and contributors
// For license information, please see license.txt

frappe.query_reports["VMG Project Budget Utilisation"] = {
	filters: [
		{
			fieldname: "project",
			label: __("Project"),
			fieldtype: "Link",
			options: "Project",
		},
		{
			fieldname: "division",
			label: __("Division"),
			fieldtype: "Link",
			options: "VMG Division",
		},
		{
			fieldname: "only_breached",
			label: __("Only Breached"),
			fieldtype: "Check",
		},
	],

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "utilisation" && data && data.utilisation > 90) {
			value = `<span style="color: var(--red-600); font-weight: bold">${value}</span>`;
		}
		if (column.fieldname === "available" && data && data.available < 0) {
			value = `<span style="color: var(--red-600); font-weight: bold">${value}</span>`;
		}
		return value;
	},
};
