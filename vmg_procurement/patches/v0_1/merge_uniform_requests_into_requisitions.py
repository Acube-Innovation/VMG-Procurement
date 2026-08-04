import frappe
from frappe.model.utils.rename_field import rename_field


def execute():
	"""VMG Staff Uniform Request is folded into VMG Purchase Requisition
	(requisition_type "Staff Uniform and PPE" + uniform_employees table):

	1. PPE handover's staff_uniform_request field becomes purchase_requisition.
	2. Each uniform request's employee rows move onto the requisition it
	   generated; reason fields are copied along.
	3. PPE links are remapped from the uniform request to that requisition.
	4. The uniform request documents, doctype, workflow and print format are
	   removed (the F03 print format now lives on VMG Purchase Requisition).
	"""
	if frappe.db.has_column("VMG PPE and Uniform Handover", "staff_uniform_request"):
		rename_field("VMG PPE and Uniform Handover", "staff_uniform_request", "purchase_requisition")

	if frappe.db.exists("DocType", "VMG Staff Uniform Request"):
		for sur in frappe.get_all(
			"VMG Staff Uniform Request",
			fields=["name", "purchase_requisition", "reason", "reason_remarks"],
		):
			pr = sur.purchase_requisition
			if not (pr and frappe.db.exists("VMG Purchase Requisition", pr)):
				continue
			frappe.db.set_value(
				"VMG Purchase Requisition",
				pr,
				{"reason": sur.reason, "reason_remarks": sur.reason_remarks},
				update_modified=False,
			)
			if not frappe.get_all(
				"VMG Uniform Request Item",
				filters={"parent": pr, "parenttype": "VMG Purchase Requisition"},
			):
				frappe.db.sql(
					"""
					update `tabVMG Uniform Request Item`
					set parent = %s, parenttype = 'VMG Purchase Requisition',
						parentfield = 'uniform_employees'
					where parent = %s and parenttype = 'VMG Staff Uniform Request'
					""",
					(pr, sur.name),
				)

		# PPE rows now hold uniform request names: follow them to the requisition
		frappe.db.sql(
			"""
			update `tabVMG PPE and Uniform Handover` ppe
			join `tabVMG Staff Uniform Request` sur on sur.name = ppe.purchase_requisition
			set ppe.purchase_requisition = sur.purchase_requisition
			"""
		)
		frappe.db.sql(
			"""
			update `tabVMG PPE and Uniform Handover` ppe
			left join `tabVMG Purchase Requisition` pr on pr.name = ppe.purchase_requisition
			set ppe.purchase_requisition = null
			where ppe.purchase_requisition is not null and pr.name is null
			"""
		)

		frappe.db.sql("delete from `tabVMG Staff Uniform Request`")
		# rows of requests that never generated a requisition have no new home
		frappe.db.sql(
			"delete from `tabVMG Uniform Request Item` where parenttype = 'VMG Staff Uniform Request'"
		)
		frappe.delete_doc("DocType", "VMG Staff Uniform Request", force=True, ignore_missing=True)

	frappe.delete_doc("Workflow", "VMG Staff Uniform Request Approval", force=True, ignore_missing=True)
	frappe.delete_doc(
		"Print Format", "VMG Staff Uniform Request VMG-PRO-F03", force=True, ignore_missing=True
	)
