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

    def _prepare_factor_file_eurof(self):
        "Called from generic module"
        self.ensure_one()
        settings = safe_eval(self.factor_journal_id.factor_settings)
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
        name = "FAA{}_{}_{}_{}.txt".format(
            settings["client"],
            self._sanitize_filepath(f"{fields.Date.today()}"),
            self.id,
            self._sanitize_filepath(self.company_id.name),
        )
        return {
            "name": name,
            "res_id": self.id,
            "res_model": self._name,
            "datas": self._prepare_factor_file_data_eurof(settings),
        }

    def _prepare_factor_file_data_eurof(self, settings):
        self.ensure_one()
        if not self.statement_date:
            # pylint: disable=C8107
            raise ValidationError("Vous devez spécifier la date du dernier relevé")
        data, max_row, balance = self._get_eurof_body(settings)
        if data:
            # raw_data = (f"{main}{RETURN}").replace("False", "    ")
            # data = clean_string(raw_data)
            # data = raw_data
            # # check there is no regression in colmuns position
            # dev_mode = tools.config.options.get("dev_mode")
            # if dev_mode and dev_mode[0][-3:] == "pdb" or False:
            #     # make debugging easier saving file on filesystem to check
            #     debug(raw_data, "_raw")
            #     debug(data)
            #     # pylint: disable=C8107
            #     raise ValidationError("See files /odoo/subrog*.txt")
            # total_in_erp = sum(self.line_ids.mapped("amount_currency"))
            # if round(balance, 2) != round(total_in_erp, 2):
            #     # pylint: disable=C8107
            #     raise ValidationError(
            #         "Erreur dans le calul de la balance :"
            #         f"\n - erp : {total_in_erp}\n - fichier : {balance}"
            #     )
            # self.write({"balance": balance})
            # non ascii chars are replaced
            data = bytes(data, "ascii", "replace").replace(b"?", b" ")
            return base64.b64encode(data)
        return False

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
        partners = self.line_ids.mapped("move_id.partner_id.commercial_partner_id")
        res = partners._check_eurof_data()
        if res:
            errors.append(res)
        partner_mapping = partners._get_partner_eurof_mapping()
        size(5, settings["client"], "client")
        size(5, settings["emetteurD"], "emetteurD")
        size(5, settings["emetteurE"], "emetteurE")
        for line in self.line_ids:
            move = line.move_id
            partner = line.move_id.partner_id.commercial_partner_id
            if not partner:
                raise ValidationError(
                    f"Pas de partenaire sur la pièce {line.move_id.name}"
                )
            ref_cli = partner_mapping.get(partner)
            if not ref_cli:
                errors.append(
                    f"Il manque un identifiant eurofactor pour '{partner.name}'"
                )
            sequence += 1
            p_type = get_type_piece(move)
            total = move.amount_total_in_currency_signed
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
            }
            if ref_cli:
                info["ref_cli"] = size(7, ref_cli, partner)
            info2 = {
                "ref_int": pad(partner.ref, 15, position="left"),
                "blanc1": pad(" ", 23),
                "ref_move": pad(move.name, 14),
                "total": pad(round(abs(total)), 15, 0),
                "date": eurof_date(move.invoice_date if p_type == "F" else move.date),
                "date_due": eurof_date(move.invoice_date_due) or pad(" ", 8),
                "paym": "A" if p_type == "F" else "T",  # TODO check si traite
                "sale": pad(move.invoice_origin if p_type == "A" else " ", 10),
                "ref_f": pad(" ", 25),  # autre ref facture
                "ref_a": pad(move.invoice_origin or " ", 14),  # ref facture de l'avoir
                "blanc2": pad(" ", 51),  # ref facture de l'avoir
                "blanc3": pad(" ", 3),  # ref facture de l'avoir
            }
            info.update(info2)
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
        return (RETURN.join(rows), len(rows), balance)


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
