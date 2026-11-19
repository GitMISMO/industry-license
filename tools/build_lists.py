"""Build the Industry License HQ scored lists.

Inputs (paths passed in order): aptify txt, member-360 terms json, encompass txt, fannie txt, freddie txt,
downloads json, cms company-contacts json, act25 json, output dir.
"""
import json, re, sys, csv, os, collections

(apt_p, terms_p, enc_p, fan_p, fred_p, dl_p, cms_p, act25_p, out_d) = sys.argv[1:10]
TODAY = '2026-11-18'

SUFFIX = r"\b(inc|incorporated|llc|l l c|ltd|limited|corp|corporation|company|co|lp|llp|pllc|plc|the|dba|na|n a|a|an|of|and)\b"
GENERIC = {'first', 'american', 'national', 'mortgage', 'credit', 'title', 'data', 'financial', 'services', 'service',
           'solutions', 'solution', 'technologies', 'technology', 'tech', 'software', 'systems', 'group', 'home', 'loan',
           'loans', 'lending', 'capital', 'partners', 'consulting', 'digital', 'united', 'premier', 'advantage',
           'global', 'bank', 'information', 'research', 'network', 'appraisal', 'valuation', 'insurance', 'real',
           'estate', 'property', 'us', 'usa', 'new', 'one', 'smart', 'secure', 'direct', 'integrated', 'professional',
           'advisors', 'advisory', 'management', 'associates', 'labs', 'ai', 'docs', 'document', 'documents', 'notary',
           'online', 'certified', 'clear', 'quality', 'best', 'standard', 'central', 'pacific', 'atlantic', 'western',
           'eastern', 'southern', 'northern', 'mid', 'mission', 'summit', 'apex', 'peak', 'core', 'prime', 'true',
           'next', 'go', 'my', 'e', 'i', 'mi', 'flood', 'fraud', 'closing', 'settlement', 'escrow', 'verification',
           'verifications', 'reporting', 'bureau', 'mortgages', 'finance', 'funding', 'analytics', 'sciences',
           'innovations', 'innovation', 'enterprises', 'holdings', 'international', 'worldwide', 'america', 'americas'}


def norm(s):
    s = (s or '').lower().replace('&', ' and ')
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(SUFFIX, " ", s)
    return re.sub(r"\s+", " ", s).strip()


def toks(name):
    return norm(name).split()


def keys_for(name):
    t = toks(name)
    return {'T:' + t[0]} if t else set()


def name_match(a, b):
    """a, b token lists. Exact, or one is a word-prefix of the other and the shorter one is distinctive."""
    if not a or not b:
        return None
    if a == b:
        return 'exact'
    s, l = (a, b) if len(a) <= len(b) else (b, a)
    if l[:len(s)] != s:
        return None
    if len(s) >= 2 and not all(w in GENERIC for w in s):
        return 'close'
    if len(s) == 1 and s[0] not in GENERIC and len(s[0]) >= 4:
        return 'close'
    return None


# ---------- Aptify companies ----------
rows = []
with open(apt_p, encoding='utf-8') as f:
    rd = csv.DictReader(f, delimiter='|')
    for r in rd:
        rows.append(r)

terms = json.load(open(terms_p))['doc']['terms']
act25 = json.load(open(act25_p))


def mismo_status(cid):
    ts = terms.get(str(cid)) or []
    if not ts:
        return 'Never', None, None
    cur = [t for t in ts if t.get('e', '') >= TODAY and t.get('s', '') <= TODAY and not t.get('x')]
    last = max(ts, key=lambda t: t.get('e', ''))
    if cur:
        c = max(cur, key=lambda t: t['e'])
        return 'Current', c.get('lv'), c.get('e')
    return 'Former', last.get('lv'), last.get('e')


# ---------- Evidence ----------
evidence = collections.defaultdict(list)  # key -> list of (strength, source, detail, listed_name)


def add(name, strength, source, detail, keyname=None):
    kt = toks(keyname or name)
    for k in keys_for(keyname or name):
        evidence[k].append((strength, source, detail, name, kt))


# Encompass Partner Connect
cats = []
for line in open(enc_p, encoding='utf-8'):
    line = line.rstrip('\n')
    if line.startswith('CATS:'):
        cats = line[5:].split('|')
        continue
    if '~' not in line:
        continue
    ci, nm = line.split('~', 1)
    base = re.split(r"\s+[-–]\s+", nm)[0]
    base = re.sub(r"\b(appraisal|flood( services| report| reportx)?|title( services| ordering| company| web| and closing)?|credit|udn|voe|voi/e|4506c|ssa89|avm|ppe|fraud|verifications?)\b.*$", "", base, flags=re.I).strip() or base
    add(nm, 'M', 'Encompass Partner Connect', cats[int(ci)] if ci.isdigit() and int(ci) < len(cats) else '', base)

# Fannie Mae lists
STRONG_FANNIE = re.compile(r"Uniform Closing Dataset|Uniform Loan Delivery|Uniform Collateral Data Portal|UAD 3\.6|eNote|eClose|eVault|Desktop Underwriter|Desktop Originator|EarlyCheck", re.I)
for line in open(fan_p, encoding='utf-8'):
    parts = line.rstrip('\n').split('~')
    if len(parts) < 3 or parts[0] not in ('IVL', 'EMORTGAGE_TSP'):
        continue
    src, nm, det = parts[0], parts[1], parts[2]
    nm_clean = re.sub(r"\(.*?\)|\*", "", nm).strip()
    if src == 'EMORTGAGE_TSP':
        add(nm_clean, 'S', 'Fannie Mae eClosing provider list', 'eMortgage technology (MISMO SMART Doc eNote)')
    else:
        add(nm_clean, 'S' if STRONG_FANNIE.search(det) else 'M', 'Fannie Mae Integrated Vendor List', det)

# Freddie Mac software providers (every Freddie interface is MISMO-based data)
for line in list(open(fred_p, encoding='utf-8'))[1:]:
    if '~' not in line:
        continue
    nm, det = line.rstrip('\n').split('~', 1)
    add(re.sub(r"[​]", "", nm).strip(), 'S', 'Freddie Mac software provider list', det)

# CMS (certified or in certification)
for nm in json.load(open(cms_p))['companies'].keys():
    add(nm, 'S', 'MISMO certification', 'Certified or in certification with MISMO')

# Website standards downloads (May 1 - Sep 8, 2026)
STD_ITEM = re.compile(r"reference-model|logical-data|ldd|dataset|smart-doc|evault|ilad|data-model|engineering-guidelines|meg-|implementation|credit-reporting|version-|v3_|v2_|mapping|schema|api|catalog|life-of-loan", re.I)
for d in json.load(open(dl_p)):
    items = d['items']
    std = sum(v for k, v in items.items() if STD_ITEM.search(k))
    detail = '%d downloads by %d people (%d standards files)' % (d['downloads'], d['people'], std)
    strength = 'M' if std else 'W'
    add(d['name'], strength, 'MISMO website downloads (May-Sep 2026)', detail)
    if not d['key'].startswith('free:'):
        stem = d['key'].split('.')[0]
        if len(stem) >= 4 and stem not in GENERIC:
            evidence['T:' + stem].append((strength, 'MISMO website downloads (May-Sep 2026)', detail + ' via ' + d['key'], d['name'], [stem]))


def find_evidence(name):
    seen, out = set(), []
    t = toks(name)
    for k in keys_for(name):
        for e in evidence.get(k, []):
            m = name_match(t, e[4])
            if not m:
                continue
            sig = (e[1], e[3])
            if sig in seen:
                continue
            seen.add(sig)
            out.append({'strength': e[0], 'source': e[1], 'detail': e[2], 'matched': e[3], 'exact': m == 'exact'})
    return out


SKIP = re.compile(r"^test |\btest company\b|^mortgage bankers association$|^mismo$", re.I)

out = []
for r in rows:
    cid, name = r['AptifyCompanyID'], r['Name']
    if SKIP.search(name or ''):
        continue
    orders = int(r['OrdersSince2022'] or 0)
    st, lv, end = mismo_status(cid)
    ev = find_evidence(name)
    strong = [e for e in ev if e['strength'] == 'S']
    med = [e for e in ev if e['strength'] == 'M']
    weak = [e for e in ev if e['strength'] == 'W']
    if strong or len({e['source'] for e in med}) >= 2:
        score = 'High'
    elif med:
        score = 'Medium'
    else:
        score = 'Low'
    reasons = []
    for e in strong + med + weak:
        reasons.append('%s%s: %s%s' % (e['source'], '' if e['exact'] else ' (close name match: ' + e['matched'] + ')',
                                       e['detail'], ''))
    if not reasons:
        reasons.append('No sign of MISMO standards in the GSE lists, Encompass Partner Connect, MISMO certifications or 2026 website downloads.')
    a25 = act25.get(str(cid))
    on_current_list = any(e['source'] != 'MISMO website downloads (May-Sep 2026)' for e in ev)
    if (a25 and a25 > 0) or on_current_list or weak or med and any('downloads' in e['source'] for e in med) or st == 'Current':
        biz = 'Likely'
        why = []
        if a25 and a25 > 0:
            why.append('%d Aptify orders since Jan 2025' % a25)
        if on_current_list:
            why.append('on a current partner or GSE list')
        if any('downloads' in e['source'] for e in ev):
            why.append('downloaded from mismo.org in 2026')
        if st == 'Current':
            why.append('current MISMO member')
        biz_why = '; '.join(why)
    else:
        biz = 'Check'
        biz_why = 'Last Aptify activity was 2022-2024 and no current list shows them; needs a web check'
    out.append({
        'id': cid, 'name': name, 'type': r['CompanyType'], 'mbaMember': r['MBAMemberType'],
        'city': r['City'], 'state': r['State'], 'ordersSince2022': orders, 'firstOrderSince2022': r['FirstOrderSince2022'],
        'ordersSince2025': a25, 'mismo': st, 'mismoLevel': lv, 'mismoEnd': end,
        'list': 'B' if st == 'Current' else ('A' if orders > 0 else None),
        'usesStandards': score, 'usesWhy': reasons, 'inBusiness': biz, 'inBusinessWhy': biz_why,
        'evidence': ev,
    })

os.makedirs(out_d, exist_ok=True)
json.dump({'built': TODAY, 'companies': out}, open(os.path.join(out_d, 'companies.json'), 'w'), indent=0)
for lst in ('A', 'B'):
    with open(os.path.join(out_d, 'list-%s.csv' % lst), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Aptify ID', 'Company', 'Type', 'MBA Member Type', 'MISMO Status', 'Last MISMO Level', 'MISMO Term End',
                    'Orders Since 2022', 'Orders Since 2025', 'Still in Business', 'Why', 'Uses MISMO Standards', 'Why'])
        for c in sorted([c for c in out if c['list'] == lst], key=lambda c: c['name'].lower()):
            w.writerow([c['id'], c['name'], c['type'], c['mbaMember'], c['mismo'], c['mismoLevel'] or '', c['mismoEnd'] or '',
                        c['ordersSince2022'], c['ordersSince2025'] if c['ordersSince2025'] is not None else '',
                        c['inBusiness'], c['inBusinessWhy'], c['usesStandards'], ' | '.join(c['usesWhy'])])

summ = collections.Counter((c['list'], c['type'], c['usesStandards'], c['inBusiness']) for c in out if c['list'])
print('List A', sum(1 for c in out if c['list'] == 'A'), 'List B', sum(1 for c in out if c['list'] == 'B'))
for lst in 'AB':
    sub = [c for c in out if c['list'] == lst]
    print(lst, collections.Counter(c['type'] for c in sub), collections.Counter(c['usesStandards'] for c in sub),
          collections.Counter(c['inBusiness'] for c in sub), collections.Counter(c['mismo'] for c in sub),
          'MBA members', sum(1 for c in sub if c['mbaMember'] not in ('Non-Member', '')))
