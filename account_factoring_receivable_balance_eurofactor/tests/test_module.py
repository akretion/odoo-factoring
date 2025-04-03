import logging

from odoo.tests.common import TransactionCase

from ..models.subrogation_receipt import get_piece_factor

logger = logging.getLogger(__name__)


class Test(TransactionCase):
    def test_get_piece_factor(self):
        def check_move_name(piece):
            move_name = get_piece_factor(piece)
            logger.debug(f"  >>>> {move_name}")
            assert len(move_name) == 14, f"Move name {move_name}"

        for piece in (
            "FAC/2025/00001",
            "RFAC/2025/00001",
            "FAC/2024/02704",
            "RFAC/2025/00016",
        ):
            check_move_name(piece)
