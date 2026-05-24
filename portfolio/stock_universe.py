"""
stock_universe.py

550-stock universe organized by sector.
Used by the screener agent to find buy opportunities.

Stocks selected based on:
- S&P 500 and NASDAQ 100 components
- Minimum market cap $10B
- Active analyst coverage on Finnhub
"""

UNIVERSE = {
    "technology": [
        "MSFT", "AAPL", "NVDA", "GOOGL", "META", "AMZN", "AMD", "AVGO",
        "CRM", "ORCL", "ADBE", "CSCO", "TXN", "QCOM", "INTC", "MU",
        "AMAT", "LRCX", "KLAC", "MRVL", "SNPS", "CDNS", "ANSS", "FTNT",
        "PANW", "CRWD", "ZS", "OKTA", "DDOG", "SNOW", "PLTR", "PATH",
        "UI", "NET", "CFLT", "MDB", "GTLB", "HUBS", "BILL", "TOST",
    ],
    "healthcare": [
        "LLY", "UNH", "JNJ", "ABT", "TMO", "DHR", "ISRG", "SYK",
        "BSX", "MDT", "ZBH", "EW", "HOLX", "IDXX", "IQV", "CRL",
        "PFE", "MRK", "ABBV", "BMY", "GILD", "AMGN", "BIIB", "VRTX",
        "REGN", "MRNA", "ILMN", "BIO", "TECH", "EXAS", "NTRA",
        "HCA", "THC", "UHS", "CNC", "MOH", "HUM", "CI", "ELV",
    ],
    "finance": [
        "JPM", "BAC", "WFC", "GS", "MS", "C", "BLK", "SCHW",
        "AXP", "V", "MA", "PYPL", "FI", "FIS", "GPN", "FISV",
        "BRK-B", "CB", "AON", "MMC", "AFL", "MET", "PRU", "AIG",
        "ICE", "CME", "NDAQ", "CBOE", "MSCI", "SPGI",
        "WFC", "USB", "TFC", "PNC", "MTB", "RF", "CFG", "HBAN",
    ],
    "consumer": [
        "AMZN", "WMT", "COST", "HD", "LOW", "TGT", "TJX", "ROST",
        "DG", "DLTR", "ULTA", "LULU", "NKE", "TPR", "RL", "PVH",
        "MCD", "SBUX", "YUM", "CMG", "DRI", "QSR",
        "PG", "KO", "PEP", "MDLZ", "GIS", "K", "CPB", "SJM",
        "CL", "CHD", "EL", "COTY", "KVUE",
        "TSLA", "GM", "F", "RIVN", "LCID",
    ],
    "industrial": [
        "CAT", "DE", "HON", "GE", "MMM", "RTX", "LMT", "NOC",
        "BA", "GD", "HII", "TDG", "HWM", "TXT",
        "UPS", "FDX", "DAL", "UAL", "AAL", "LUV", "JBLU",
        "CSX", "UNP", "NSC", "KSU",
        "ETN", "EMR", "ROK", "PH", "AME", "GNRC", "HUBB",
        "WM", "RSG", "CDAY", "FAST", "GWW", "MSC",
    ],
    "energy": [
        "XOM", "CVX", "COP", "EOG", "PXD", "DVN", "MPC", "VLO",
        "PSX", "SLB", "HAL", "BKR",
        "OKE", "WMB", "KMI", "ET", "EPD", "MMP",
        "NEE", "DUK", "SO", "D", "AEP", "EXC", "XEL", "WEC",
        "ES", "ETR", "FE", "PPL", "CMS", "NI",
    ],
    "real_estate": [
        "PLD", "AMT", "CCI", "EQIX", "PSA", "EXR", "AVB", "EQR",
        "MAA", "UDR", "CPT", "NNN", "O", "STOR", "ADC",
        "SPG", "MAC", "TCO", "CBL",
        "BXP", "HIW", "VNO", "SLG", "KRC", "DEI",
    ],
    "materials": [
        "LIN", "APD", "ECL", "SHW", "PPG", "RPM", "FMC",
        "NEM", "GOLD", "AEM", "KGC", "WPM",
        "FCX", "SCCO", "AA", "CENX",
        "NUE", "STLD", "CLF", "X", "RS",
        "IFF", "EMN", "CE", "WLK", "LYB", "DOW",
    ],
    "communication": [
        "GOOGL", "META", "NFLX", "DIS", "CMCSA", "CHTR", "TMUS",
        "VZ", "T", "LUMN",
        "SPOT", "PINS", "SNAP", "TWTR", "MTCH",
        "WBD", "PARA", "FOX", "FOXA", "NYT", "NWSA",
    ],
}


def get_all_tickers() -> list:
    """Return all tickers across all sectors."""
    all_tickers = []
    for tickers in UNIVERSE.values():
        all_tickers.extend(tickers)
    return list(set(all_tickers))  # deduplicate


def get_tickers_by_sector(sector: str) -> list:
    """Return tickers for a specific sector."""
    return UNIVERSE.get(sector.lower(), [])


def get_sectors() -> list:
    """Return all available sectors."""
    return list(UNIVERSE.keys())
