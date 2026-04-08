from odoo import fields, models
import json
import base64

class AccountMove(models.Model):
    _inherit = 'account.move'

    def _compute_json_qr(self):
        for rec in self:
            dict_invoice = None
            if rec.move_type in ['out_invoice','out_refund'] and rec.state == 'posted' and rec.afip_auth_code:
                try:
                    dict_invoice = {
                        "ver": 1,
                        "fecha": str(rec.invoice_date),
                        "cuit": int(rec.company_id.partner_id.vat),
                        "ptoVta": rec.journal_id.l10n_ar_afip_pos_number,
                        "tipoCmp": int(rec.l10n_latam_document_type_id.code),
                        "nroCmp": int(rec.name.split('-')[2]),
                        "importe": rec.amount_total,
                        "moneda": rec.currency_id.l10n_ar_afip_code,
                        "ctz": rec.l10n_ar_currency_rate,
                        "tipoDocRec": int(rec.partner_id.l10n_latam_identification_type_id.l10n_ar_afip_code),
                        "nroDocRec": int(rec.partner_id.vat),
                        "tipoCodAut": 'E',
                        "codAut": int(rec.afip_auth_code),
                        }
                except:
                    dict_invoice = None
            if dict_invoice:
                res = json.dumps(dict_invoice)
                rec.json_qr = res
                b64 = base64.b64encode(res.encode('utf-8')).decode('utf-8')
                rec.texto_modificado_qr = 'https://www.afip.gob.ar/fe/qr/?p=' + b64
            else:
                rec.json_qr = ''
                rec.texto_modificado_qr = ''

    json_qr = fields.Char("JSON QR AFIP", compute=_compute_json_qr)
    texto_modificado_qr = fields.Char('Texto Modificado QR', compute=_compute_json_qr)
