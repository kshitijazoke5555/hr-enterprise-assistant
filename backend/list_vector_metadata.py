from backend.rag_pipeline import get_vectorstore

vs = get_vectorstore()
print('Vectorstore persist dir:', getattr(vs, 'persist_directory', 'unknown'))

try:
    coll = getattr(vs, '_collection', None)
    if coll is None:
        print('No internal _collection attribute; attempting similarity_search fallback')
        docs = vs.similarity_search('policy', k=50)
        metas = [getattr(d, 'metadata', {}) for d in docs]
    else:
        print('Using internal collection.get() to list metadata...')
        data = coll.get()
        metas = data.get('metadatas') or []

    dept_counts = {}
    country_counts = {}
    sample = []
    for m in metas:
        if not m:
            continue
        md = {k.lower(): v for k, v in m.items()}
        dept = md.get('department') or md.get('dept') or ''
        country = md.get('country') or ''
        dept_counts[dept] = dept_counts.get(dept, 0) + 1
        country_counts[country] = country_counts.get(country, 0) + 1
        if len(sample) < 10:
            sample.append({'department': dept, 'country': country, 'policy_name': md.get('policy_name') or md.get('source')})

    # List distinct policy_name/source entries that have missing department or country
    missing_dept = set()
    missing_country = set()
    for m in metas:
        if not m:
            continue
        md = {k.lower(): v for k, v in m.items()}
        dept = (md.get('department') or '').strip()
        country = (md.get('country') or '').strip()
        name = (md.get('policy_name') or md.get('source') or '').strip()
        if not dept and name:
            missing_dept.add(name)
        if not country and name:
            missing_country.add(name)

    print('Department counts:', dept_counts)
    print('Country counts:', country_counts)
    print('Sample metadata (up to 10):')
    for s in sample:
        print(' -', s)
    if missing_dept:
        print('\nPolicy files missing `department` metadata:')
        for n in sorted(missing_dept):
            print(' -', n)
    if missing_country:
        print('\nPolicy files missing `country` metadata:')
        for n in sorted(missing_country):
            print(' -', n)
except Exception as e:
    print('Error while listing metadata:', e)
    try:
        docs = vs.similarity_search('policy', k=20)
        for d in docs:
            print('DOC META:', d.metadata)
    except Exception as e2:
        print('Fallback similarity_search failed:', e2)
