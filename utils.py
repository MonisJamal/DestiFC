def parse_number(value: str) -> int:
    if value is None:
        return None
    if isinstance(value, int) or isinstance(value, float):
        return int(value)
    val = str(value).lower().replace(",", "").replace(" ", "").strip()
    mult = 1
    if val.endswith('k'):
        mult = 1_000
        val = val[:-1]
    elif val.endswith('m'):
        mult = 1_000_000
        val = val[:-1]
    elif val.endswith('b'):
        mult = 1_000_000_000
        val = val[:-1]
    elif val.endswith('t'):
        mult = 1_000_000_000_000
        val = val[:-1]
    try:
        return int(float(val) * mult)
    except ValueError:
        return 0
