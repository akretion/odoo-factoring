# © 2024 David BEAL @ Akretion
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import base64
import inspect
import re

from odoo import fields, models
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval

from .account_journal import ini_format_to_dict

RETURN = "\r\n"


class SubrogationReceipt(models.Model):
    _inherit = "subrogation.receipt"

    def _factor_settings(self):
        return safe_eval(self.factor_journal_id.factor_settings)

    def _prepare_factor_file_eurof(self):
        "Called from generic module"
        self.ensure_one()
        if not self.statement_date:
            # pylint: disable=C8107
            raise ValidationError("Vous devez spécifier la date du dernier relevé")
        settings = self._factor_settings()
        missing_keys = []
        for key in ini_format_to_dict(
            self.env["res.company"]._populate_eurof_settings()
        ):
            if not settings.get(key):
                missing_keys.append(key)
        if missing_keys:
            raise ValidationError(
                f"Le journal doit comporter les clés suivantes {missing_keys} "
                "avec des valeurs correctes"
            )
        data = []
        lines, max_row, balance = self._get_eurof_body(settings)
        if not lines:
            return []
        file_date = self._sanitize_filepath(f"{fields.Date.today()}")
        company_ = self._sanitize_filepath(self.company_id.name)
        # On peut avoir 2 fichiers
        my_lines = {"emetteurD": [], "emetteurE": []}
        for emetteur in my_lines.keys():
            for line in lines:
                if settings[emetteur] in line:
                    my_lines[emetteur].append(line)
            file_data = bytes(RETURN.join(my_lines[emetteur]), "ascii", "replace")
            name = f"FAA{settings[emetteur]}_{file_date}_{company_}_{self.id}.txt"
            data.append(
                {
                    "name": name,
                    "res_id": self.id,
                    "res_model": self._name,
                    "datas": base64.b64encode(file_data.replace(b"?", b" ")),
                }
            )
        return data

    def _sanitize_filepath(self, string):
        string = super()._sanitize_filepath(string)
        if self.factor_type == "eurof":
            string = string.replace("-", "_")
        return string

    def _get_eurof_body(self, settings):
        errors = []

        def size(size, data, info=None):
            field = False
            if info and isinstance(info, models.Model):
                if hasattr(info, data):
                    field = data
                    data = info[data]
            res = check_size(data, size, info=info, field=field)
            if res:
                errors.append(res)
            else:
                return data

        self = self.sudo()
        sequence = 1
        rows = []
        balance = 0
        partner_mapping = self.env["res.partner"]._get_partner_eurof_mapping()
        size(5, settings["client"], "client")
        size(5, settings["emetteurD"], "emetteurD")
        size(5, settings["emetteurE"], "emetteurE")
        for line in self.line_ids:
            move = line.move_id
            partner = line.move_id.commercial_partner_id
            partner_ident = False
            if partner_mapping.get(move.partner_shipping_id):
                partner_ident = move.partner_shipping_id
            elif partner_mapping.get(move.commercial_partner_id):
                partner_ident = move.commercial_partner_id
            else:
                errors.append(
                    f"Il manque un identifiant eurofactor pour la pièce '{move.name}'"
                )
            ref_cli = partner_mapping.get(partner_ident)
            res = partner._check_eurof_data()
            if res:
                errors.append(res)
            sequence += 1
            p_type = get_type_piece(move)
            total = abs(move.amount_total_in_currency_signed)
            activity = "E"
            if partner.country_id == self.env.ref("base.fr"):
                activity = "D"
            info = {
                "emetteur": settings["emetteurD"]
                if activity == "D"
                else settings["emetteurE"],
                "client": settings["client"],
                "file_date": eurof_date(fields.Date.today()),
                "activity": activity,
                "afc": "711" if activity == "D" else "999",
                "p_type": p_type,
                "devise": move.currency_id.name,
                "ref_cli": size(7, ref_cli or "", partner),
                "ref_int": pad(partner.ref, 15, position="left"),
                "blanc1": pad(" ", 23),
                "ref_move": pad(cut(move.name, 14), 14, position="left"),
                "total": pad(str(round(total, 2)).replace(".", ""), 15, 0),
                "date": eurof_date(move.invoice_date if p_type == "F" else move.date),
                "date_due": eurof_date(move.invoice_date_due),
                "paym": "A" if p_type == "F" else "T",  # TODO check si traite
                "sale": pad(cut(move.invoice_origin, 10), 10, position="left"),
                "ref_f": pad(" ", 25),  # autre ref facture
                "ref_a": pad(
                    cut(move.invoice_origin, 14) if p_type == "A" else " ", 14
                ),  # ref facture de l'avoir
                "blanc2": pad(" ", 51),  # ref facture de l'avoir
                "blanc3": pad(" ", 3),  # ref facture de l'avoir
            }
            responses = check_required(info, line.name)
            if responses:
                errors.extend(responses)
            infos = [val for k, val in info.items()]
            if infos:
                string = ";".join([x or "" for x in infos]) + ";"
                rows.append(string)
        for row in rows:
            res = check_column_size(row)
            if res:
                errors.append(res)
        if errors:
            self.warn = "\n%s" % "\n".join(errors)
            return False, False, False
        return (rows, len(rows), balance)

    def _compute_instruction(self):
        """Display mail where send file"""
        res = super()._compute_instruction()
        for rec in self:
            instruction = ""
            if rec.factor_type == "eurof":
                settings = safe_eval(self.factor_journal_id.factor_settings)
                mail_prod = settings.get("mail_prod")
                if mail_prod:
                    instruction = (
                        "Les fichiers de quittance sont à joindre "
                        f"à l'adresse ' {mail_prod} '. Un seul fichier par mail\n"
                        "Le mail ne doit contenir que le fichier sans signature "
                        "ni image."
                    )
            rec.instruction = rec.instruction or instruction
        return res

    def _amount_eurof_rpt(self, france=True):
        lines = self._eurof_lines_rpt(france)
        return sum(lines.mapped("debit")) - sum(lines.mapped("credit"))

    def _eurof_lines_rpt(self, france=True):
        if france:
            return self.line_ids.filtered(
                lambda s: s.partner_shipping_id.country_id == s.env.ref("base.fr")
            )
        else:
            return self.line_ids.filtered(
                lambda s: not s.partner_shipping_id.country_id == s.env.ref("base.fr")
            )

    def _eurof_labels_rpt(self):
        line = self.line_ids and self.line_ids[0]
        return line._eurof_fields_rpt().keys()


def get_piece_factor(name, p_type):
    if not p_type:
        return "{}{}".format(name[:15], pad(" ", 15))
    return name[:30]


def get_type_piece(move):
    # journal_type = move.journal_id.type
    p_type = False
    move_type = move.move_type
    if move_type == "out_invoice":
        p_type = "F"
    elif move_type == "out_refund":
        p_type = "A"
    assert len(p_type) == 1
    return p_type


def pad(string, pad, end=" ", position="right"):
    "Complete string by leading `end` string from `position`"
    check_string(string)
    if isinstance(end, int | float):
        end = str(end)
    if isinstance(string, int | float):
        string = str(string)
    if position == "right":
        string = string.rjust(pad, end)
    else:
        string = string.ljust(pad, end)
    return string


def cut(string, size):
    res = string
    if not string:
        res = " " * size
    elif len(string) > size:
        res = string[-size:]
    return res


def check_size(string, size, info=None, field=None):
    res = check_string(string, info=info, field=field)
    if res:
        return res
    if len(string) != size:
        inspect_string = inspect_code(inspect.stack()[2], string, info)
        return f"{inspect_string}\n\tLa taille de '{string}' devrait etre de {size}\n"
    return False


def check_string(string, info=None, field=None):
    if not isinstance(string, str):
        return (
            f"{inspect_code(inspect.stack()[3], string, info, field)}\n\t"
            "La chaine fournie est vide.\n"
        )
    return False


def check_required(infos, name):
    required = [
        "emetteur",
        "client",
        "p_type",
        "devise",
        "ref_cli",
        "ref_int",
        "ref_move",
        "total",
        "date_due",
    ]
    messages = []
    for key in required:
        datum = infos[key]
        if datum:
            datum = datum.replace(" ", "")
        if not datum:
            messages.append(f"La donnée '{key}' pour '{name}' est manquante.")
    return messages


def inspect_code(stack, string, info=None, field=None):
    data = ""
    if info and isinstance(info, models.Model):
        if info:
            data += f" sur le {info._description} '{info.display_name}'"
            if field:
                data += f", Champ: '{info._fields[field].string}'"
    return data


def clean_string(string):
    """Remove all except [A-Z], space, \r, \n
    https://www.rapidtables.com/code/text/ascii-table.html"""
    string = string.upper()
    string = re.sub(r"[\x21-\x2F]|[\x3A-\x40]|[\x5E-\x7F]|\x0A\x0D", r" ", string)
    return string


def debug(content, suffix=""):
    mpath = f"/odoo/subrog{suffix}.txt"
    with open(mpath, "wb") as f:
        if isinstance(content, str):
            content = bytes(content, "ascii", "replace")
        f.write(content)


def check_column_size(string):
    if len(string) != 240:
        # pylint: disable=C8107
        return (
            f"\nLa ligne suivante contient {len(string)} caractères au lieu de 240\n"
            f"{string}"
        )


def eurof_date(date_field):
    return date_field.strftime("%Y%m%d")
