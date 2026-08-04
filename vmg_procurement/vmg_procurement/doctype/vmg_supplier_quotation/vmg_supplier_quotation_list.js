// Copyright (c) 2026, VMG and contributors
// For license information, please see license.txt

frappe.listview_settings["VMG Supplier Quotation"] = {
	add_fields: ["status"],

	get_indicator(doc) {
		const colours = {
			"Draft": "red",
			"Submitted": "blue",
			"Selected": "green",
			"Not Selected": "gray",
			"Expired": "orange",
			"Cancelled": "red",
		};
		if (doc.status && colours[doc.status]) {
			return [__(doc.status), colours[doc.status], "status,=," + doc.status];
		}
	},
};
