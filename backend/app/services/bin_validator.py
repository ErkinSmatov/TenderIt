"""Kazakhstan 12-digit BIN (Business Identification Number) validator.

BIN structure:
  Positions 1-2 : Registration year (last 2 digits)
  Positions 3-4 : Registration month
  Position  5   : Entity type — 4=resident legal entity, 5=non-resident, 6=IE joint venture
  Position  6   : Unit type — 0=head, 1=branch, 2=representation
  Positions 7-11: Sequential number
  Position  12  : Check digit

Source: lookuptax.com/docs/tax-identification-number/kazakhstan-tax-id-guide
"""


def validate_bin(bin_str: str) -> bool:
    """Validate Kazakhstan 12-digit BIN format and checksum.

    Returns True only if:
    - bin_str is exactly 12 ASCII digits
    - Position 5 (index 4) is '4', '5', or '6' (legal entity check, not IIN)
    - The check digit at position 12 (index 11) passes the two-cycle checksum algorithm
    """
    if not bin_str or not bin_str.isdigit() or len(bin_str) != 12:
        return False
    # Position 5 (index 4) must be 4, 5, or 6 — rejects IIN (individual) inputs
    if bin_str[4] not in ("4", "5", "6"):
        return False
    digits = [int(d) for d in bin_str]
    # First weight cycle: weights 1..11
    weights1 = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
    total = sum(d * w for d, w in zip(digits[:11], weights1))
    check = total % 11
    if check == 10:
        # Second weight cycle: weights [3,4,5,6,7,8,9,10,11,1,2]
        weights2 = [3, 4, 5, 6, 7, 8, 9, 10, 11, 1, 2]
        total2 = sum(d * w for d, w in zip(digits[:11], weights2))
        check = total2 % 11
        if check == 10:
            check = 0
    return check == digits[11]
