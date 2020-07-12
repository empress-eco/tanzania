# -*- coding: utf-8 -*-
# Copyright (c) 2020, Aakvatech and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
# from frappe import _
from frappe.utils import today
from frappe.model.document import Document
from erpnext.stock.utils import get_latest_stock_qty, get_stock_balance


class SpecialClosingBalance(Document):
	def on_submit(self):
		items = []
		user_remarks = "Special Closing Balance - {0}".format(self.name)
		for item_row in self.closing_balance_details:
			if item_row.item and item_row.quantity != None:
				item_balance = get_latest_stock_qty(item_row.item, self.warehouse) or 0
				item_row.item_balance = item_balance
				item_row.db_update()
				if item_row.quantity != item_balance:
					item_dict = dict(
						item_code=item_row.item,
						qty=item_row.quantity - item_balance,
						uom=item_row.uom,
						s_warehouse=self.warehouse
					)
					items.append(item_dict)
		stock_entry_doc = frappe.get_doc(dict(
				doctype="Stock Entry",
				posting_date=self.posting_date,
				set_posting_time = 1,
				items=items,
				stock_entry_type='Material Receipt',
				purpose='Material Receipt',
				to_warehouse=self.warehouse,
				company=self.company,
				remarks=user_remarks,
				special_closing_balance=self.name
				)).insert(ignore_permissions=True)
		if stock_entry_doc:
			frappe.flags.ignore_account_permission = True
			stock_entry_doc.submit()
			# return stock_entry_doc.name
			self.stock_entry = stock_entry_doc.name
			url = frappe.utils.get_url_to_form(stock_entry_doc.doctype, stock_entry_doc.name)
			frappe.msgprint("Stock Entry Created <a href='{0}'>{1}</a>".format(url,stock_entry_doc.name))

@frappe.whitelist()
def get_items(warehouse, posting_date, posting_time, company):
	lft, rgt = frappe.db.get_value("Warehouse", warehouse, ["lft", "rgt"])

	items = frappe.db.sql("""
		select i.name, i.item_name, i.stock_uom, id.default_warehouse
		from tabItem i, `tabItem Default` id
		where i.name = id.parent
			and exists(select name from `tabWarehouse` where lft >= %s and rgt <= %s and name=id.default_warehouse)
			and i.is_stock_item = 1 and i.has_serial_no = 0 and i.has_batch_no = 0
			and i.has_variants = 0 and i.disabled = 0 and id.company=%s
		group by i.name
		order by i.name
	""", (lft, rgt, company), as_list=True)

	res = []
	for d in items:
		stock_bal = get_stock_balance(d[0], d[3], posting_date, posting_time,
			with_valuation_rate=True)

		if frappe.db.get_value("Item", d[0], "disabled") == 0:
			res.append({
				"item": d[0],
				"uom": d[2],
				"warehouse": d[3],
				"quantity": stock_bal[0],
				"item_name": d[1],
				"valuation_rate": stock_bal[1],
				"item_balance": stock_bal[0],
				"current_valuation_rate": stock_bal[1]
			})

	return res