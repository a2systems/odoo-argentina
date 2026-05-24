# -*- coding: utf-8 -*-

from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError,ValidationError
from odoo.tools import float_is_zero, pycompat
from odoo.addons import decimal_precision as dp
from datetime import date
import os
import base64
from collections import defaultdict

class AccountMove(models.Model):
        _inherit = 'account.move'

        def action_post(self):
            if self.move_type in ['out_invoice','out_refund']:
                self.compute_taxes()
            return super(AccountMove, self).action_post()
        

        def _compute_tax_amounts(self):
            for rec in self:
                if rec.move_tax_ids:
                    if rec.move_type in ['out_invoice','out_refund']:
                        vat_taxable_amount = 0
                        other_taxes_amount = 0
                        vat_exempt_base_amount = 0
                        vat_amount = 0
                        for move_tax in rec.move_tax_ids:
                            if move_tax.tax_id.tax_group_id.tax_type == 'vat' and move_tax.tax_id.tax_group_id.l10n_ar_vat_afip_code != '2':
                                vat_taxable_amount += move_tax.base_amount
                                vat_amount += move_tax.tax_amount
                            elif move_tax.tax_id.tax_group_id.l10n_ar_vat_afip_code == '2':
                                vat_exempt_base_amount += move_tax.base_amount
                            else:
                                other_taxes_amount += move_tax.tax_amount
                        rec.vat_taxable_amount = vat_taxable_amount
                        rec.vat_amount = vat_amount
                        rec.other_taxes_amount = other_taxes_amount
                        rec.vat_exempt_base_amount = vat_exempt_base_amount
                        rec.vat_untaxed_base_amount = 0
                    else:
                        rec.vat_taxable_amount = 0
                        rec.vat_amount = 0
                        rec.other_taxes_amount = 0
                        rec.vat_exempt_base_amount = 0
                        rec.vat_untaxed_base_amount = 0
                else:
                   rec.vat_taxable_amount = 0
                   rec.vat_amount = 0
                   rec.other_taxes_amount = 0
                   rec.vat_exempt_base_amount = 0
                   rec.vat_untaxed_base_amount = 0

        def compute_taxes(self):
            self.ensure_one()
            if self.state == 'draft':
                if self.move_type == 'entry':
                    return
                for move_tax in self.move_tax_ids:
                    move_tax.unlink()
                if self.move_type in ['out_invoice','out_refund']:
                    for line in self.line_ids:
                        tax = self.env['account.tax'].search([('name','=',line.name),('type_tax_use','=','sale')])
                        if tax:
                            vals = {
                                'move_id': self.id,
                                'tax_id': tax.id,
                                'invoice_date': self.invoice_date,
                                'partner_id': self.partner_id.id,
                                'l10n_latam_document_type_id': self.l10n_latam_document_type_id.id,
                                'l10n_ar_afip_responsibility_type_id': self.partner_id.l10n_ar_afip_responsibility_type_id.id,
                                'state_id': self.partner_id.state_id.id,
                                'move_type': self.move_type,
                                }
                            if self.move_type == 'out_invoice':
                                vals['tax_amount'] = line.credit
                            else:
                                vals['tax_amount'] = line.debit
                            base_amount = 0
                            for inv_line in self.invoice_line_ids:
                                if inv_line.tax_ids and tax.id in inv_line.tax_ids.ids:
                                    base_amount = base_amount + inv_line.price_subtotal
                            vals['base_amount'] = base_amount
                            move_tax_id = self.env['account.move.tax'].create(vals)

                else:
                    for invoice_line in self.invoice_line_ids:
                        if invoice_line.tax_ids:
                            for tax in invoice_line.tax_ids.ids:
                                account_tax = self.env['account.tax'].browse(tax)
                                move_tax_id = self.env['account.move.tax'].search([('move_id','=',self.id),('tax_id','=',tax)])
                                if not move_tax_id:
                                    vals = {
                                        'move_id': self.id,
                                        'tax_id': tax,
                                        'invoice_date': self.invoice_date,
                                        'partner_id': self.partner_id.id,
                                        'l10n_latam_document_type_id': self.l10n_latam_document_type_id.id,
                                        'l10n_ar_afip_responsibility_type_id': self.partner_id.l10n_ar_afip_responsibility_type_id.id,
                                        'state_id': self.partner_id.state_id.id,
                                        'move_type': self.move_type,
                                        }
                                    move_tax_id = self.env['account.move.tax'].create(vals)
                                move_tax_id.base_amount = move_tax_id.base_amount + invoice_line.price_subtotal
                                if account_tax.tax_group_id.tax_type == 'vat':
                                    move_tax_id.tax_amount = move_tax_id.tax_amount + invoice_line.price_subtotal * (account_tax.amount / 100)
                                else:
                                    tax_amount = 0
                                    for line in self.line_ids:
                                        if line.name == move_tax_id.tax_id.name:
                                            tax_amount = tax_amount + line.debit or line.credit
                                    move_tax_id.tax_amount = move_tax_id.tax_amount + tax_amount


        move_tax_ids = fields.One2many(comodel_name='account.move.tax',inverse_name='move_id',string='Impuestos')
        vat_taxable_amount = fields.Float('Base imponible de IVA',compute=_compute_tax_amounts)
        vat_amount = fields.Float('Monto de IVA',compute=_compute_tax_amounts)
        other_taxes_amount = fields.Float('Monto de Otros Impuestos',compute=_compute_tax_amounts)
        vat_exempt_base_amount = fields.Float('Monto de IVA',compute=_compute_tax_amounts)
        vat_untaxed_base_amount = fields.Float('Monto de IVA no gravado',compute=_compute_tax_amounts)

class AccountMoveTax(models.Model):
        _name = 'account.move.tax'
        _description = 'account.move.tax'

        move_id = fields.Many2one('account.move',string='Factura')
        tax_id = fields.Many2one('account.tax',string='Impuesto')
        base_amount = fields.Float('Monto base')
        tax_amount = fields.Float('Impuesto')
        partner_id = fields.Many2one(comodel_name='res.partner',string='Cliente/Proveedor')
        l10n_latam_document_type_id = fields.Many2one('l10n_latam.document.type',string='Tipo de documento')
        invoice_date = fields.Date('Fecha de factura')
        state_id = fields.Many2one('res.country.state',string='Provincia')
        l10n_ar_afip_responsibility_type_id = fields.Many2one('l10n_ar.afip.responsibility.type',string='Responsabilidad AFIP')
        move_type = fields.Selection(selection=[
            ('entry', 'Journal Entry'),
            ('out_invoice', 'Customer Invoice'),
            ('out_refund', 'Customer Credit Note'),
            ('in_invoice', 'Vendor Bill'),
            ('in_refund', 'Vendor Credit Note'),
            ('out_receipt', 'Sales Receipt'),
            ('in_receipt', 'Purchase Receipt'),
            ], string='Type')

class AccountTaxGroup(models.Model):
        _inherit = 'account.tax.group'

        tax_type = fields.Selection(selection=[('vat','IVA'),('withholdings','Percepciones/Retenciones'),('exempt','Exentos')],string='Tipo de Impuestos')

