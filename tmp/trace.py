def get_traces():
    with open('tmp/summary_logs.txt', 'r', encoding='utf-8') as f:
        text = f.read().replace('\r', '\n')
    lines = text.split('\n')
    capture = False
    out_lines = []
    for line in lines:
        if 'test_004' in line:
             capture = True
        if 'test_005' in line:
             break
        if capture and line.strip() and "complete  |  scheduled" not in line:
             out_lines.append(line.strip())
             
    with open('tmp/trace_logs.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(out_lines))

get_traces()
