def find_blog():
    with open('tmp/summary_logs.txt', 'r', encoding='utf-8') as f:
        text = f.read().replace('\r', '\n')
    lines = text.split('\n')
    res = []
    for l in lines:
        if 'tulsi' in l.lower() or 'draft' in l.lower():
            if 'Monitoring: 6 draft' not in l:
                res.append(l.strip())
    
    with open('tmp/tulsi.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(res[-30:]))
find_blog()
