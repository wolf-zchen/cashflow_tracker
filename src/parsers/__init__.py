"""
Parser factory for auto-detecting and using the correct parser.
"""
from pathlib import Path
from typing import Optional

from .base_parser import BaseParser
from .monarch_parser import MonarchParser
from .chase_credit_parser import ChaseCreditParser
from .chase_checking_parser import ChaseCheckingParser
from .amex_csv_parser import AmexCsvParser
from .amex_parser import AmexParser
from .bofa_parser import BofAParser
from .capital_one_parser import CapitalOneParser


# All available parsers — ORDER MATTERS.
# MonarchParser must come first: its column set is distinct and must win
# before the generic Chase/Amex parsers try to claim the file.
ALL_PARSERS = [
    MonarchParser(),      # Monarch Money exports (all accounts in one file)
    ChaseCreditParser(),
    ChaseCheckingParser(),
    AmexCsvParser(),
    AmexParser(),         # Excel format (must follow CSV Amex check)
    BofAParser(),
    CapitalOneParser(),
]


def detect_parser(file_path: Path) -> Optional[BaseParser]:
    """
    Auto-detect which parser to use for a given file.

    Args:
        file_path: Path to the file to parse

    Returns:
        The appropriate parser, or None if no parser matches
    """
    for parser in ALL_PARSERS:
        if parser.detect(file_path):
            return parser
    return None


def get_parser_info(file_path: Path) -> Optional[dict]:
    """
    Get information about which parser would be used for a file.

    Args:
        file_path: Path to the file to check

    Returns:
        Dictionary with parser info, or None if no parser matches
    """
    parser = detect_parser(file_path)
    if parser:
        return {
            'institution': parser.institution,
            'account_type': parser.account_type,
            'parser_class': parser.__class__.__name__
        }
    return None


__all__ = [
    'BaseParser',
    'MonarchParser',
    'ChaseCreditParser',
    'ChaseCheckingParser',
    'AmexCsvParser',
    'AmexParser',
    'BofAParser',
    'CapitalOneParser',
    'detect_parser',
    'get_parser_info',
    'ALL_PARSERS'
]
