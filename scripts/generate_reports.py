import os, json
from pathlib import Path
from datetime import datetime, timezone
import requests

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / 'data'
ARCHIVE_DIR = DATA_DIR / 'archive'
DATA_DIR.mkdir(parents=True, exist_ok=True)
ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

FINNHUB_API_KEY = os.getenv('FINNHUB_API_KEY', '')
ALPHA_VANTAGE_API_KEY = os.getenv('ALPHA_VANTAGE_API_KEY', '')
FMP_API_KEY = os.getenv('FMP_API_KEY', '')
FRED_API_KEY = os.getenv('FRED_API_KEY', '')
NOW_UTC = datetime.now(timezone.utc)
TODAY = NOW_UTC.strftime('%Y-%m-%d')
NOW_LABEL = NOW_UTC.strftime('%Y-%m-%d %H:%M UTC')


def save_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def safe_get_json(url, params=None):
    try:
        r = requests.get(url, params=params or {}, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def get_finnhub_quote(symbol):
    if not FINNHUB_API_KEY:
        return None
    return safe_get_json('https://finnhub.io/api/v1/quote', {'symbol': symbol, 'token': FINNHUB_API_KEY})


def get_finnhub_news():
    if not FINNHUB_API_KEY:
        return []
    data = safe_get_json('https://finnhub.io/api/v1/news', {'category': 'general', 'token': FINNHUB_API_KEY})
    return data[:6] if isinstance(data, list) else []


def get_finnhub_economic_calendar():
    if not FINNHUB_API_KEY:
        return []
    data = safe_get_json('https://finnhub.io/api/v1/calendar/economic', {'from': TODAY, 'to': TODAY, 'token': FINNHUB_API_KEY})
    return data.get('economicCalendar', [])[:6] if isinstance(data, dict) else []


def get_finnhub_market_status():
    if not FINNHUB_API_KEY:
        return None
    return safe_get_json('https://finnhub.io/api/v1/stock/market-status', {'exchange': 'US', 'token': FINNHUB_API_KEY})


def get_alpha_news():
    if not ALPHA_VANTAGE_API_KEY:
        return []
    data = safe_get_json('https://www.alphavantage.co/query', {'function': 'NEWS_SENTIMENT', 'tickers': 'SPY,QQQ', 'apikey': ALPHA_VANTAGE_API_KEY})
    return data.get('feed', [])[:4] if isinstance(data, dict) else []


def get_alpha_top_movers():
    if not ALPHA_VANTAGE_API_KEY:
        return []
    data = safe_get_json('https://www.alphavantage.co/query', {'function': 'TOP_GAINERS_LOSERS', 'apikey': ALPHA_VANTAGE_API_KEY})
    if not isinstance(data, dict):
        return []
    out = []
    for item in data.get('top_gainers', [])[:2] + data.get('top_losers', [])[:2]:
        out.append({'asset': item.get('ticker', 'n/a'), 'move': item.get('change_percentage', 'n/a'), 'driver': 'Alpha Vantage top movers feed'})
    return out[:4]


def get_alpha_treasury(maturity='10year'):
    if not ALPHA_VANTAGE_API_KEY:
        return None
    data = safe_get_json('https://www.alphavantage.co/query', {'function': 'TREASURY_YIELD', 'interval': 'daily', 'maturity': maturity, 'apikey': ALPHA_VANTAGE_API_KEY})
    if isinstance(data, dict) and isinstance(data.get('data'), list) and data['data']:
        return data['data'][0].get('value')
    return None


def get_fmp_sector_performance():
    if not FMP_API_KEY:
        return []
    data = safe_get_json('https://financialmodelingprep.com/api/v3/sectors-performance', {'apikey': FMP_API_KEY})
    if not isinstance(data, list):
        return []
    return [{'sector': item.get('sector', 'Unknown'), 'move': item.get('changesPercentage', 'n/a'), 'note': 'FMP sectors-performance feed'} for item in data[:6]]


def get_breadth_snapshot():
    if not ALPHA_VANTAGE_API_KEY:
        return None
    data = safe_get_json('https://www.alphavantage.co/query', {'function': 'TOP_GAINERS_LOSERS', 'apikey': ALPHA_VANTAGE_API_KEY})
    if not isinstance(data, dict):
        return None
    gainers = data.get('top_gainers', [])
    losers = data.get('top_losers', [])
    most_active = data.get('most_actively_traded', [])
    return {'gainers_count': len(gainers), 'losers_count': len(losers), 'active_count': len(most_active)}


def get_vix_latest():
    if FRED_API_KEY:
        data = safe_get_json('https://api.stlouisfed.org/fred/series/observations', {'series_id': 'VIXCLS', 'api_key': FRED_API_KEY, 'file_type': 'json', 'sort_order': 'desc', 'limit': 1})
        if isinstance(data, dict) and isinstance(data.get('observations'), list) and data['observations']:
            return data['observations'][0].get('value')
    quote = get_finnhub_quote('^VIX')
    if isinstance(quote, dict) and quote.get('c') is not None:
        return str(quote.get('c'))
    return None


def pct_move(current, prev_close):
    if current is None or prev_close in (None, 0):
        return None
    return round(((current - prev_close) / prev_close) * 100, 2)


def fmt_move(v):
    return 'n/a' if v is None else f"{'+' if v >= 0 else ''}{v:.2f}%"


def tone(v):
    return 'blue' if v is None else ('pos' if v >= 0 else 'neg')


def parse_num(value):
    try:
        return float(str(value).replace('%', '').replace('+', '').replace(',', '').strip())
    except Exception:
        return None


def build_metrics():
    symbols = [('SPY', 'S&P proxy'), ('QQQ', 'Nasdaq proxy'), ('DIA', 'Dow proxy'), ('IWM', 'Russell proxy')]
    metrics = []
    for symbol, label in symbols:
        q = get_finnhub_quote(symbol)
        if isinstance(q, dict):
            move = pct_move(q.get('c'), q.get('pc'))
            metrics.append({'label': label, 'value': fmt_move(move), 'tone': tone(move), 'raw_move': move})
    if not metrics:
        metrics = [
            {'label': 'S&P proxy', 'value': 'API pending', 'tone': 'blue', 'raw_move': None},
            {'label': 'Nasdaq proxy', 'value': 'API pending', 'tone': 'blue', 'raw_move': None},
            {'label': 'Dow proxy', 'value': 'API pending', 'tone': 'blue', 'raw_move': None},
            {'label': 'Russell proxy', 'value': 'API pending', 'tone': 'blue', 'raw_move': None},
        ]
    vix = get_vix_latest()
    y10 = get_alpha_treasury('10year')
    metrics.append({'label': 'VIX', 'value': vix or 'pending', 'tone': 'blue', 'raw_move': None})
    metrics.append({'label': 'US10Y', 'value': f'{y10}%' if y10 else 'pending', 'tone': 'blue', 'raw_move': None})
    return metrics[:6]


def build_headlines():
    out = []
    for item in get_finnhub_news():
        if isinstance(item, dict) and item.get('headline'):
            out.append(item['headline'])
    for item in get_alpha_news():
        if isinstance(item, dict) and item.get('title'):
            out.append(item['title'])
    return out[:6] or [
        'Live headlines will appear here once API keys are configured.',
        'The summary remains the first analytical block in the final dashboard structure.',
        'You can still replace or enrich sources later without changing the reading flow.'
    ]


def build_macro():
    rows = []
    for item in get_finnhub_economic_calendar():
        if isinstance(item, dict):
            rows.append({'time': item.get('time', 'n/a'), 'event': item.get('event', 'Unknown event'), 'status': item.get('impact', 'Watch')})
    return rows[:5] or [{'time': 'n/a', 'event': 'Economic calendar pending API connection', 'status': 'Connect Finnhub key'}]


def build_movers():
    return get_alpha_top_movers() or [
        {'asset': 'NVDA', 'move': '+0.0%', 'driver': 'Alpha Vantage movers pending'},
        {'asset': 'MSFT', 'move': '+0.0%', 'driver': 'Alpha Vantage movers pending'}
    ]


def build_sectors():
    return get_fmp_sector_performance() or [
        {'sector': 'Technology', 'move': '+0.0%', 'note': 'FMP sectors pending'},
        {'sector': 'Financials', 'move': '+0.0%', 'note': 'FMP sectors pending'}
    ]


def build_context():
    breadth = get_breadth_snapshot() or {'gainers_count': 0, 'losers_count': 0, 'active_count': 0}
    status = get_finnhub_market_status() or {}
    vix = get_vix_latest()
    y2 = get_alpha_treasury('2year')
    y10 = get_alpha_treasury('10year')
    return {
        'breadth': breadth,
        'market_status': status,
        'vix': vix,
        '2y': y2,
        '10y': y10,
    }


def build_scoring(metrics, sectors, context):
    score = 0
    reasons = []
    metric_moves = [m.get('raw_move') for m in metrics if isinstance(m.get('raw_move'), (int, float))]
    sector_moves = [parse_num(s.get('move')) for s in sectors]
    sector_moves = [x for x in sector_moves if x is not None]
    avg_metric = sum(metric_moves) / len(metric_moves) if metric_moves else 0
    avg_sector = sum(sector_moves) / len(sector_moves) if sector_moves else 0
    if avg_metric > 0.35:
        score += 2; reasons.append('Index proxies positive')
    elif avg_metric < -0.35:
        score -= 2; reasons.append('Index proxies negative')
    if avg_sector > 0.2:
        score += 1; reasons.append('Sector breadth supportive')
    elif avg_sector < -0.2:
        score -= 1; reasons.append('Sector breadth weak')
    vix = parse_num(context.get('vix'))
    if vix is not None:
        if vix < 18:
            score += 1; reasons.append('VIX relatively calm')
        elif vix > 24:
            score -= 1; reasons.append('VIX elevated')
    breadth = context.get('breadth', {})
    if breadth.get('gainers_count', 0) > breadth.get('losers_count', 0):
        score += 1; reasons.append('Gainers exceed losers in snapshot')
    elif breadth.get('gainers_count', 0) < breadth.get('losers_count', 0):
        score -= 1; reasons.append('Losers exceed gainers in snapshot')
    regime = 'Balanced / neutral'
    if score >= 3:
        regime = 'Risk-on confirmation'
    elif score == 2:
        regime = 'Constructive risk-on'
    elif score <= -3:
        regime = 'Risk-off confirmation'
    elif score <= -2:
        regime = 'Cautious risk-off'
    return {'score': score, 'regime': regime, 'reasons': reasons[:4]}


def build_summary(report_type, metrics, headlines, macro, movers, sectors, context, scoring):
    mode_text = 'פתיחה' if report_type == 'open' else 'סגירה'
    metric_text = ', '.join([f"{m['label']} {m['value']}" for m in metrics[:4]])
    macro_event = macro[0]['event'] if macro else 'No macro event loaded'
    top_headline = headlines[0] if headlines else 'No live headline loaded'
    top_mover = movers[0]['asset'] if movers else 'No mover loaded'
    top_sector = sectors[0]['sector'] if sectors else 'No sector loaded'
    breadth = context.get('breadth', {})
    market_open = context.get('market_status', {}).get('isOpen')
    market_state = 'open' if market_open is True else 'closed / pending'
    vix = context.get('vix') or 'pending'
    y10 = context.get('10y') or 'pending'
    return [
        f'זהו בלוק 10 נקודות הסיכום של דוח {mode_text}, והוא נשאר ראשון במסך גם בגרסה הסופית.',
        f'מצב השוק לפי מנוע הניקוד: {scoring["regime"]} (score {scoring["score"]}).',
        f'סטטוס המסחר בארה"ב כרגע: {market_state}.',
        f'תמונת המדדים/פרוקסים כרגע: {metric_text}.',
        f'מדד התנודתיות VIX עומד על {vix}, ותשואת אג"ח ארה"ב ל-10 שנים על {y10}%.',
        f'תמונת breadth מה-snapshot: gainers {breadth.get("gainers_count",0)} מול losers {breadth.get("losers_count",0)}.',
        f'אירוע המאקרו המרכזי שזוהה: {macro_event}.',
        f'המניה הבולטת ב-feed של movers היא {top_mover}, והסקטור הראשון בפיד הוא {top_sector}.',
        'הסיכום העליון כבר משלב metrics, macro, movers, sectors, volatility, yields ו-breadth.',
        f'דוגמת headline חי שנקלט: {top_headline}'
    ]


def build_report(report_type='open'):
    metrics = build_metrics()
    headlines = build_headlines()
    macro = build_macro()
    movers = build_movers()
    sectors = build_sectors()
    context = build_context()
    scoring = build_scoring(metrics, sectors, context)
    return {
        'schema_version': '3.0-final-starter',
        'report_type': report_type,
        'report_date': TODAY,
        'generated_at': NOW_LABEL,
        'report_window': 'Final starter architecture',
        'market_regime': scoring['regime'],
        'sub_title': 'המסך הסופי כולל summary ראשון, metrics, movers, sectors, macro, headlines, breadth, VIX, yields ו-scoring engine',
        'hero_title': 'Opening report final architecture' if report_type == 'open' else 'Closing report final architecture',
        'hero_text': 'זוהי גרסה כמעט סופית של המערכת: תצוגת דוח אחידה, pipeline מתוזמן, ושכבות נתונים חיות שמזינות קודם כל את עשר נקודות הסיכום.',
        'movers_title': 'Live movers',
        'badges': [
            {'label': 'FINAL STARTER', 'class': 'live'},
            {'label': '10-POINT SUMMARY FIRST', 'class': 'macro'},
            {'label': 'SCORING ENGINE', 'class': 'info'}
        ],
        'metrics': [{'label': m['label'], 'value': m['value'], 'tone': m['tone']} for m in metrics],
        'summary': build_summary(report_type, metrics, headlines, macro, movers, sectors, context, scoring),
        'movers': movers,
        'sectors': sectors,
        'macro': macro,
        'headlines': headlines,
        'tomorrow_setup': [
            'הפוקוס עכשיו צריך לעבור מחיבור מקורות לבקרת איכות של הטקסטים והדאטה.',
            'אפשר לכוונן את scoring thresholds לפי סגנון הקריאה שאתה אוהב.',
            'מבנית, זה כבר קרוב מאוד לתוצר סופי לשימוש יומי.'
        ],
        'pipeline_status': {
            'data_freshness': 'final starter integration',
            'generator': 'scripts/generate_reports.py',
            'environment': 'github-actions with FINNHUB_API_KEY, ALPHA_VANTAGE_API_KEY, FMP_API_KEY, FRED_API_KEY',
            'scoring_reasons': scoring['reasons']
        }
    }


def write_archive(report):
    archive_name = f"{report['report_date']}-{report['report_type']}.json"
    save_json(ARCHIVE_DIR / archive_name, report)
    return {'date': report['report_date'], 'mode': report['report_type'], 'label': f"{report['report_date']} {report['report_type'].title()}", 'file': archive_name}


def merge_archive_index(new_items):
    index_path = ARCHIVE_DIR / 'index.json'
    existing = []
    if index_path.exists():
        try:
            existing = json.loads(index_path.read_text(encoding='utf-8')).get('items', [])
        except Exception:
            existing = []
    merged, seen = [], set()
    for item in new_items + existing:
        key = (item['date'], item['mode'])
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    save_json(index_path, {'items': merged[:30]})


def main():
    new_items = []
    for report_type in ['open', 'close']:
        report = build_report(report_type)
        save_json(DATA_DIR / f'{report_type}-report.json', report)
        new_items.append(write_archive(report))
    merge_archive_index(new_items)


if __name__ == '__main__':
    main()
