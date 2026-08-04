// Copyright (c) 2026, VMG and contributors
// For license information, please see license.txt

// Division-driven fetches (cost_center, project, site_engineer,
// division_manager) are declared as fetch_from in the DocType and run
// automatically when the division changes.

frappe.ui.form.on("VMG Purchase Requisition", {
	refresh(frm) {
		toggle_emergency_indicator(frm);
		add_create_buttons(frm);
		set_default_print_format(frm);
	},

	requisition_type(frm) {
		set_default_print_format(frm);
	},

	is_emergency(frm) {
		toggle_emergency_indicator(frm);
	},
});

// Create buttons appear only on submitted, workflow-Approved requisitions.
// The server decides the allowed targets (asset -> Material Request only;
// otherwise RFQ, plus direct LPO for the procurement manager), so the UI can
// never offer both chains at once.
function add_create_buttons(frm) {
	if (frm.doc.docstatus !== 1 || frm.doc.workflow_state !== "Approved") return;

	const buttons = {
		"Material Request": [__("Material Request"), "make_material_request"],
		"VMG Request for Quotation": [__("Request for Quotation"), "make_vmg_rfq"],
		"VMG Local Purchase Order": [__("Local Purchase Order"), "make_vmg_lpo"],
	};

	frappe
		.call({
			method: "vmg_procurement.utils.routing.get_allowed_targets",
			args: { requisition_name: frm.doc.name },
		})
		.then((r) => {
			(r.message || []).forEach((target) => {
				const [label, method] = buttons[target];
				frm.add_custom_button(
					label,
					() =>
						frappe.model.open_mapped_doc({
							method: "vmg_procurement.utils.routing." + method,
							frm: frm,
						}),
					__("Create")
				);
			});
		});
}

// The emergency flag renders as a red dashboard headline only. Never touch
// frm.page.set_indicator / clear_indicator here: that slot belongs to the
// standard workflow-state pill next to the document id, and clearing it on
// refresh wipes the workflow status from the form.
function toggle_emergency_indicator(frm) {
	if (frm.doc.is_emergency) {
		frm.dashboard.set_headline_alert(
			`<span class="indicator-pill red">${__("Emergency Purchase")}</span>`
		);
	} else {
		frm.dashboard.clear_headline();
	}
}

// F01 is the general requisition form; Staff Uniform and PPE requisitions
// print on the F03 staff-uniform layout instead
function set_default_print_format(frm) {
	frm.meta.default_print_format =
		frm.doc.requisition_type === "Staff Uniform and PPE"
			? "VMG Purchase Requisition VMG-PRO-F03"
			: "VMG Purchase Requisition VMG-PRO-F01";
}
