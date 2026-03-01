def extract_logs():
    with open('tmp/summary_logs.txt', 'r', encoding='utf-8') as f:
        content = f.read()

    # Split on Date marker "Mar 01" to get clean lines
    import re
    lines = content.split("Mar 01 ")
    clean_lines = []
    for l in lines:
        if not l.strip(): continue
        # Removing completely any weird carriage returns
        text = l.replace('\r', ' ').replace('\n', ' ')
        clean_lines.append(f"Mar 01 {text}")

    output_lines = []
    for i, l in enumerate(clean_lines):
        if 'test_00' in l or 'WhatsApp sent' in l or 'intent=' in l or 'chanakya' in l or 'health scan' in l or 'draft blog' in l or 'sab fix karo' in l:
            output_lines.append(f"--> {l[:200]}")

    with open('tmp/clean_summary.txt', 'w', encoding='utf-8') as out:
        out.write('\n'.join(output_lines))

extract_logs()
