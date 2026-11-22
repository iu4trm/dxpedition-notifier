PREFIX_TO_CONTINENT: dict[str, str] = {
    # --- EUROPA (EU) ---
    "I": "EU", "IA": "EU", "IB": "EU", "IC": "EU", "ID": "EU", "IE": "EU", "IF": "EU",
    "IG": "EU", "IH": "EU", "II": "EU", "IJ": "EU", "IK": "EU", "IL": "EU", "IM": "EU",
    "IN": "EU", "IO": "EU", "IP": "EU", "IQ": "EU", "IR": "EU", "IS": "EU", "IT": "EU", "IU": "EU",
    "DL": "EU", "DA": "EU", "DB": "EU", "DC": "EU", "DD": "EU", "DE": "EU", "DF": "EU",
    "DG": "EU", "DH": "EU", "DJ": "EU", "DK": "EU", "DM": "EU", "DN": "EU", "DO": "EU",
    "DP": "EU", "DQ": "EU", "DR": "EU",
    "F": "EU", "TM": "EU",
    "G": "EU", "M": "EU", "2E": "EU",
    "GW": "EU", "MW": "EU", "2W": "EU",
    "GM": "EU", "MM": "EU", "2M": "EU",
    "GI": "EU", "MI": "EU", "2I": "EU",
    "GJ": "EU", "MJ": "EU", "2J": "EU",
    "GU": "EU", "MU": "EU", "2U": "EU",
    "EA": "EU", "EB": "EU", "EC": "EU", "ED": "EU", "EE": "EU", "EF": "EU", "EG": "EU", "EH": "EU",
    "EA6": "EU", "AM": "EU", "AO": "EU",
    "CT": "EU", "CU": "EU",
    "HB9": "EU", "HB0": "EU", "HE": "EU",
    "OE": "EU", "ON": "EU", "OO": "EU", "OP": "EU", "OQ": "EU", "OR": "EU", "OS": "EU", "OT": "EU",
    "PA": "EU", "PB": "EU", "PC": "EU", "PD": "EU", "PE": "EU", "PF": "EU", "PG": "EU", "PH": "EU", "PI": "EU",
    "SM": "EU", "SA": "EU", "SB": "EU", "SC": "EU", "SD": "EU", "SE": "EU", "SF": "EU",
    "SG": "EU", "SH": "EU", "SI": "EU", "SJ": "EU", "SK": "EU", "SL": "EU", "7S": "EU", "8S": "EU",
    "OH": "EU", "OF": "EU", "OG": "EU", "OI": "EU", "OJ": "EU",
    "LA": "EU", "LB": "EU", "LC": "EU", "LD": "EU", "LE": "EU", "LF": "EU", "LG": "EU",
    "LH": "EU", "LI": "EU", "LJ": "EU", "LN": "EU",
    "SP": "EU", "SQ": "EU", "SN": "EU", "SO": "EU", "SR": "EU", "3Z": "EU", "HF": "EU",
    "OK": "EU", "OL": "EU", "OM": "EU",
    "HA": "EU", "HG": "EU",
    "YO": "EU", "YP": "EU", "YQ": "EU", "YR": "EU",
    "LZ": "EU",
    "SV": "EU", "SW": "EU", "SX": "EU", "SY": "EU", "SZ": "EU", "J4": "EU", "SV5": "EU", "SV9": "EU",
    "9A": "EU", "S5": "EU", "E7": "EU", "YT": "EU", "YU": "EU", "Z3": "EU", "4O": "EU", "ZA": "EU",
    "LY": "EU", "YL": "EU", "ES": "EU", "ER": "EU", "EW": "EU", "EU": "EU",
    "UR": "EU", "UT": "EU", "UW": "EU", "UX": "EU", "UY": "EU", "UZ": "EU", "EM": "EU", "EN": "EU", "EO": "EU",
    "EI": "EU", "EJ": "EU", "LX": "EU", "OZ": "EU", "5P": "EU", "5Q": "EU", "TF": "EU", "9H": "EU",

    # --- NORD AMERICA (NA) ---
    "K": "NA", "W": "NA", "N": "NA",
    "AA": "NA", "AB": "NA", "AC": "NA", "AD": "NA", "AE": "NA", "AF": "NA",
    "AG": "NA", "AH": "NA", "AI": "NA", "AJ": "NA", "AK": "NA", "AL": "NA",
    "KL": "NA", "KP4": "NA", "KP2": "NA", "KP3": "NA", "KG4": "NA",
    "VE": "NA", "VA": "NA", "VY": "NA", "VO": "NA", "CF": "NA", "CG": "NA", "CH": "NA", "CI": "NA", "CJ": "NA", "CK": "NA",
    "XE": "NA", "XF": "NA",
    "TI": "NA", "HP": "NA", "YN": "NA", "TG": "NA", "YS": "NA", "HR": "NA",
    "CO": "NA", "CM": "NA", "HI": "NA", "VP9": "NA", "ZF": "NA", "6Y": "NA", "J3": "NA", "J6": "NA", "J7": "NA", "J8": "NA", "8P": "NA", "9Y": "NA", "FG": "NA", "FM": "NA", "FS": "NA",

    # --- SUD AMERICA (SA) ---
    "PY": "SA", "PP": "SA", "PQ": "SA", "PR": "SA", "PS": "SA", "PT": "SA", "PU": "SA", "PV": "SA", "PW": "SA", "PX": "SA", "ZY": "SA", "ZZ": "SA",
    "LU": "SA", "LW": "SA", "AY": "SA", "AZ": "SA", "L2": "SA", "L9": "SA",
    "CE": "SA", "CA": "SA", "CB": "SA", "CC": "SA", "CD": "SA", "XQ": "SA", "XR": "SA", "3G": "SA",
    "CX": "SA", "CV": "SA", "CW": "SA",
    "ZP": "SA",
    "CP": "SA",
    "OA": "SA", "OB": "SA", "OC": "SA", "4T": "SA",
    "HC": "SA", "HD": "SA",
    "HK": "SA", "HJ": "SA", "5K": "SA",
    "YV": "SA", "YW": "SA", "YX": "SA", "YY": "SA", "4M": "SA",
    "FY": "SA", "PZ": "SA", "8R": "SA",

    # --- AFRICA (AF) ---
    "CN": "AF", "5C": "AF", "5D": "AF", "5E": "AF", "5F": "AF", "5G": "AF",
    "7X": "AF", "3V": "AF", "5A": "AF", "SU": "AF",
    "EA8": "AF", "EA9": "AF", "CT3": "AF", "D4": "AF", "6W": "AF", "9G": "AF", "5N": "AF", "5U": "AF", "5V": "AF", "TU": "AF", "EL": "AF", "TR": "AF", "TN": "AF", "9Q": "AF", "9U": "AF", "9X": "AF", "XT": "AF", "TY": "AF",
    "ZS": "AF", "ZR": "AF", "ZT": "AF", "ZU": "AF",
    "7Q": "AF", "9J": "AF", "Z2": "AF", "A2": "AF", "3DA": "AF", "7P": "AF",
    "5H": "AF", "5X": "AF", "5Z": "AF", "ET": "AF", "J2": "AF", "ST": "AF",
    "5R": "AF", "3B8": "AF", "3B9": "AF", "FR": "AF", "FH": "AF", "S7": "AF", "VQ9": "AF",

    # --- ASIA (AS) ---
    "JA": "AS", "JE": "AS", "JF": "AS", "JG": "AS", "JH": "AS", "JI": "AS", "JJ": "AS", "JK": "AS", "JL": "AS", "JM": "AS", "JN": "AS", "JO": "AS", "JP": "AS", "JQ": "AS", "JR": "AS", "JS": "AS", "7J": "AS", "7K": "AS", "7L": "AS", "7M": "AS", "7N": "AS", "8J": "AS", "8K": "AS", "8L": "AS", "8M": "AS", "8N": "AS",
    "HL": "AS", "DS": "AS", "6K": "AS", "6L": "AS", "6M": "AS", "6N": "AS", "D7": "AS", "D8": "AS", "D9": "AS", "DT": "AS",
    "BY": "AS", "BA": "AS", "BD": "AS", "BG": "AS", "BH": "AS", "BI": "AS", "BJ": "AS", "BL": "AS", "BM": "AS", "BN": "AS", "BO": "AS", "BP": "AS", "BQ": "AS", "BR": "AS", "BS": "AS", "BT": "AS", "BU": "AS", "BV": "AS", "BW": "AS", "BX": "AS", "VR": "AS", "XX9": "AS",
    "UA": "AS", "UB": "AS", "UC": "AS", "UD": "AS", "UE": "AS", "UF": "AS", "UG": "AS", "UH": "AS", "UI": "AS", "R": "AS",
    "VU": "AS", "VT": "AS", "VW": "AS", "4P": "AS", "4Q": "AS", "4R": "AS", "4S": "AS", "9N": "AS", "A5": "AS", "S2": "AS", "AP": "AS", "AR": "AS", "AS": "AS",
    "HS": "AS", "E2": "AS", "9M": "AS", "9V": "AS", "YB": "AS", "YC": "AS", "YD": "AS", "YE": "AS", "YF": "AS", "YG": "AS", "YH": "AS", "YI": "AS", "DU": "AS", "DV": "AS", "DW": "AS", "DX": "AS", "DY": "AS", "DZ": "AS", "4F": "AS", "4G": "AS", "4H": "AS", "4I": "AS", "XV": "AS", "3W": "AS", "XU": "AS", "XW": "AS", "XY": "AS", "XZ": "AS",
    "4X": "AS", "4Z": "AS", "OD": "AS", "JY": "AS", "YK": "AS", "HZ": "AS", "7Z": "AS", "A4": "AS", "A6": "AS", "A7": "AS", "A9": "AS", "9K": "AS", "EP": "AS", "EQ": "AS", "YA": "AS", "UK": "AS", "UN": "AS", "EY": "AS", "EX": "AS", "EZ": "AS", "4K": "AS", "4J": "AS", "EK": "AS",

    # --- OCEANIA (OC) ---
    "VK": "OC", "AX": "OC", "VI": "OC", "VJ": "OC", "VL": "OC", "VM": "OC", "VN": "OC", "VZ": "OC",
    "ZL": "OC", "ZM": "OC", "ZK": "OC",
    "KH6": "OC", "WH6": "OC", "AH6": "OC", "NH6": "OC",
    "KH0": "OC", "KH2": "OC", "T8": "OC", "V6": "OC", "V7": "OC", "3D2": "OC", "FK": "OC", "FO": "OC", "FW": "OC", "YJ": "OC", "P2": "OC", "H4": "OC", "5W": "OC", "ZK3": "OC",
}

SORTED_PREFIXES = sorted(PREFIX_TO_CONTINENT.keys(), key=len, reverse=True)


def get_call_continent(callsign: str) -> str | None:
    """
    Restituisce il codice continente ('EU', 'NA', 'SA', 'AF', 'AS', 'OC')
    in base al prefisso del nominativo, gestendo anche eventuali barre '/'.
    """
    call = (callsign or "").strip().upper()
    if not call:
        return None

    parts = [p.strip() for p in call.split("/") if p.strip()]
    candidates = sorted(parts, key=len) + [call] if len(parts) > 1 else [call]

    for cand in candidates:
        for prefix in SORTED_PREFIXES:
            if cand.startswith(prefix):
                return PREFIX_TO_CONTINENT[prefix]

    return None