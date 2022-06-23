# © 2022 David BEAL @ Akretion
# © 2022 Alexis DE LATTRE @ Akretion
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import base64
import re

from odoo import fields, models, tools
from odoo.exceptions import UserError, RedirectWarning


FORMAT_VERSION = "7.0"
RETURN = "\r\n"


class SubrogationReceipt(models.Model):
    _inherit = "subrogation.receipt"

    def _prepare_factor_file_bpce(self):
        self.ensure_one
        name = "BPCE_%s_%s_%s.txt" % (
            self._sanitize_filepath("%s" % fields.Date.today()),
            self.id,
            self._sanitize_filepath(self.company_id.name),
        )
        return {
            "name": name,
            "res_id": self.id,
            "res_model": self._name,
            "datas": self._prepare_factor_file_data_bpce(),
        }

    def _prepare_factor_file_data_bpce(self):
        """"""

        def check_column_position(content, final=True):
            line2 = content.split(RETURN)[1]
            # line2 = content.readline(2)
            currency = line2[177:180]
            msg = "Problème de décalage colonne dans le fichier"
            if final:
                msg += " final"
            else:
                msg += " brut"
            assert currency == self.factor_journal_id.currency_id.name, msg

        if not self.company_id.bpce_factor_code:
            raise UserError(
                "Vous devez mettre le code du factor dans la société '%s'.\n"
                "Champ dans l'onglet 'Factor'" % self.env.company.name
            )
        if not self.statement_date:
            raise UserError("Vous devez spécifier la date du dernier relevé")
        body, max_row, balance = self._get_bpce_body()
        header = self._get_bpce_header(max_row)
        ender = self._get_bpce_ender(max_row, balance)
        raw_data = ("%s%s%s%s" % (header, RETURN, body, ender)).replace("False", "    ")
        data = clean_string(raw_data)
        # check there is no regression in colmuns position
        # check_column_position(raw_data, False)
        # check_column_position(data)
        dev_mode = tools.config.options.get("dev_mode")
        if dev_mode and dev_mode[0][-3:] == "pdb" or False:
            # make debugging easier saving file on filesystem to check
            debug(raw_data, "_raw")
            debug(data)
            raise UserError("See files /odoo/subrog*.txt")
        # non ascii chars are replaced
        data = bytes(data, "ascii", "replace").replace(b"?", b"\\")
        return base64.b64encode(data)

    def _get_bpce_header(self, max_row):
        self = self.sudo()
        info = {
            "seq": pad(max_row + 2, 6, 0),
            "code": pad(self.company_id.bpce_factor_code, 6, 0),
            "devise": self.factor_journal_id.currency_id.name,
            "name": pad(self.company_id.partner_id.name, 25),
            "statem_date": bpce_date(self.statement_date),
            "date": bpce_date(self.date),
            "idfile": pad(self.id, 3, 0),
            "reserved": pad(" ", 208),
            "format": FORMAT_VERSION,
        }
        string = "01{seq}138{code}{devise}{name}{statem_date}{date}"
        string += "{idfile}{format}{reserved}"
        return string.format(**info)

    def _get_bpce_ender(self, max_row, balance):
        self = self.sudo()
        info = {
            "seq": pad(max_row + 2, 6, 0),
            "code": pad(self.company_id.bpce_factor_code, 6, 0),
            "name": pad(self.company_id.partner_id.name[:25], 25),
            "balance": pad(round(balance * 100), 13, 0),
            "reserved": pad(" ", 220),
        }
        return "09{seq}138{code}{name}{balance}{reserved}".format(**info)

    def _get_bpce_body(self):
        """ """
        self = self.sudo()
        sequence = 1
        rows = []
        for move in self.move_ids:
            partner = move.partner_id.commercial_partner_id
            sequence += 1
            name = pad(move.name, 30)
            p_type = get_type_piece(move.move_type, move.journal_id.type)
            balance = 0
            total = move.amount_total_in_currency_signed
            info = {
                "seq": pad(sequence, 6, 0),
                "siret": pad(partner.siret or "", 14, position="right"),
                "pname": pad(partner.name[:15], 15),
                "ref_cli": pad(partner.ref, 10),
                "res1": pad(" ", 5),
                "activity": "E",  # TODO manage between Domestique/Export
                "res2": pad(" ", 9),
                "cmt": pad(" ", 20),
                "piece": name,
                "piece_factor": get_piece_factor(name, p_type),
                "type": p_type,
                "paym": "VIR"
                if p_type == "FAC"
                else "   ",  # TODO only VIR is implemented
                "date": bpce_date(move.invoice_date if p_type == "FAC" else move.date),
                "date_due": bpce_date(move.invoice_date_due) or pad(" ", 8),
                "total": pad(round(abs(total) * 100), 13, 0),
                "devise": move.currency_id.name,
                "res3": "  ",
                "eff_non_echu": " ",  # TODO
                "eff_num": pad(" ", 7),  # TODO
                "eff_total": pad("", 13, 0),  # effet total TODO not implemented
                "eff_imputed": pad("", 13, 0),  # effet imputé TODO not implemented
                "rib": pad(" ", 23),  # TODO
                "eff_echeance": pad(" ", 8),  # date effet echeance TODO not implemented
                "eff_pull": pad(" ", 10),  # reférence tiré/le nom TODO not implemented
                "eff_type": " ",  # 0: traite non accepté, 1: traite accepté, 2: BOR TODO not implemented
                "res4": pad(" ", 17),
            }
            balance += total
            string = "02{seq}{siret}{pname}{ref_cli}{res1}{activity}{res2}{cmt}"
            string += "{piece}{piece_factor}{type}{paym}{date}{date_due}{total}"
            string += "{devise}{res3}{eff_total}{eff_imputed}{eff_echeance}{eff_pull}"
            string += "{eff_type}{res4}"
            print(string.format(**info))
            rows.append(string.format(**info))
        return (RETURN.join(rows), len(rows), balance)


def get_piece_factor(name, p_type):
    if not p_type:
        return "%s%s" % (name[:15], pad(" ", 15))
    return name[:30]


def get_type_piece(move_type, journal_type):
    "in_invoice/refund, in/out_receipt   sale/purchase/cash/bank/general"
    p_type = False
    if move_type == "entry":
        if journal_type == "general":
            p_type = "ODC"
    elif move_type == "out_invoice":
        p_type = "FAC"
    elif move_type == "out_refund":
        p_type = "AVO"
    assert len(p_type) == 3
    return p_type


def bpce_date(date_field):
    return date_field.strftime("%d%m%Y")


def pad(string, pad, end=" ", position="left"):
    "Complete string by leading `end` string from `position`"
    if isinstance(end, (int, float)):
        end = str(end)
    if isinstance(string, (int, float)):
        string = str(string)
    if position == "left":
        string = string.rjust(pad, end)
    else:
        string = string.ljust(pad, end)
    return string


def clean_string(string):
    """Remove all except [A-Z], space, \\, \r, \n
    https://www.rapidtables.com/code/text/ascii-table.html"""
    string = string.replace(FORMAT_VERSION, "FORMATVERSION")
    string = string.upper()
    string = re.sub(r"[\x21-\x2F]|[\x3A-\x40]|[\x5E-\x7F]|\x0A\x0D", r"\\", string)
    string = string.replace("FORMATVERSION", FORMAT_VERSION)
    return string


def debug(content, suffix=""):
    mpath = "/odoo/subrog%s.txt" % suffix
    with open(mpath, "wb") as f:
        if isinstance(content, str):
            content = bytes(content, "ascii", "replace")
        f.write(content)
